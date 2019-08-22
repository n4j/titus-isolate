import json
from datetime import datetime, timedelta
from dateutil.parser import parse
import kubernetes.client
import kubernetes.config
from kubernetes.client.rest import ApiException
from kubernetes.client.models import V1beta1CustomResourceDefinition, V1beta1CustomResourceDefinitionNames, \
                                     V1beta1CustomResourceDefinitionSpec, V1beta1CustomResourceDefinitionVersion, \
                                     V1DeleteOptions, V1ObjectMeta, V1OwnerReference

from titus_isolate import log
from titus_isolate.config.constants import EC2_LOCAL_IPV4, TOTAL_THRESHOLD, DEFAULT_TOTAL_THRESHOLD, \
                                           OVERSUBSCRIBE_CLEANUP_AFTER_SECONDS_KEY, \
                                           DEFAULT_OVERSUBSCRIBE_CLEANUP_AFTER_SECONDS, \
                                           OVERSUBSCRIBE_WINDOW_SIZE_MINUTES_KEY, \
                                           DEFAULT_OVERSUBSCRIBE_WINDOW_SIZE_MINUTES
from titus_isolate.event.constants import ACTION, OVERSUBSCRIBE
from titus_isolate.event.event_handler import EventHandler
from titus_isolate.metrics.constants import OVERSUBSCRIBE_FAIL_COUNT, OVERSUBSCRIBE_SKIP_COUNT, \
                                            OVERSUBSCRIBE_SUCCESS_COUNT, OVERSUBSCRIBE_RECLAIMED_CPU_COUNT, \
                                            OVERSUBSCRIBE_CONSUMED_CPU_COUNT
from titus_isolate.metrics.metrics_reporter import MetricsReporter
from titus_isolate.model.opportunistic_resource import OpportunisticResource, OPPORTUNISTIC_RESOURCE_GROUP, \
                                                       OPPORTUNISTIC_RESOURCE_VERSION, OPPORTUNISTIC_RESOURCE_KIND, \
                                                       OPPORTUNISTIC_RESOURCE_NAMESPACE, \
                                                       OPPORTUNISTIC_RESOURCE_SINGULAR, OPPORTUNISTIC_RESOURCE_PLURAL, \
                                                       OPPORTUNISTIC_RESOURCE_NAME, \
                                                       OPPORTUNISTIC_RESOURCE_FIELD_SELECTOR
from titus_isolate.model.opportunistic_resource_capacity import OpportunisticResourceCapacity
from titus_isolate.model.opportunistic_resource_spec import OpportunisticResourceSpec
from titus_isolate.model.opportunistic_resource_window import OpportunisticResourceWindow
from titus_isolate.predict.cpu_usage_predictor import PredEnvironment
from titus_isolate.utils import get_config_manager, get_workload_monitor_manager, get_cpu_usage_predictor_manager

CRD_VERSION = 'apiextensions.k8s.io/v1beta1'
CRD_KIND = 'CustomResourceDefinition'

VIRTUAL_KUBELET_CONFIG_PATH = '/run/virtual-kubelet.config'
KUBECONFIG_ENVVAR = 'KUBECONFIG'
DEFAULT_KUBECONFIG_PATH = '/run/kubernetes/config'

def get_kubeconfig_path():
    with open(VIRTUAL_KUBELET_CONFIG_PATH) as file:
        line = file.readline()
        while line:
            if line.startswith(KUBECONFIG_ENVVAR+'='):
                return line.strip()[len(KUBECONFIG_ENVVAR)+1:]
            line = file.readline()
    return DEFAULT_KUBECONFIG_PATH

class OversubscribeEventHandler(EventHandler, MetricsReporter):

    def __init__(self, workload_manager):
        super().__init__(workload_manager)
        self.__reg = None
        self.__fail_count = 0
        self.__skip_count = 0
        self.__success_count = 0
        self.__reclaimed_cpu_count = 0
        self.__consumed_cpu_count = 0

        self.__config_manager = get_config_manager()
        self.__workload_monitor_manager = get_workload_monitor_manager()
        self.__cpu_usage_predictor_manager = get_cpu_usage_predictor_manager()

        self.__node_name = self.__config_manager.get_str(EC2_LOCAL_IPV4)
        kubeconfig = get_kubeconfig_path()
        self.__core_api = kubernetes.client.CoreV1Api(
            kubernetes.config.new_client_from_config(config_file=kubeconfig))
        self.__ext_api = kubernetes.client.ApiextensionsV1beta1Api(
            kubernetes.config.new_client_from_config(config_file=kubeconfig))
        self.__custom_api = kubernetes.client.CustomObjectsApi(
            kubernetes.config.new_client_from_config(config_file=kubeconfig))

    def set_registry(self, registry):
        self.__reg = registry

    def report_metrics(self, tags):
        self.__reg.gauge(OVERSUBSCRIBE_FAIL_COUNT, tags).set(self.get_fail_count())
        self.__reg.gauge(OVERSUBSCRIBE_SKIP_COUNT, tags).set(self.get_skip_count())
        self.__reg.gauge(OVERSUBSCRIBE_SUCCESS_COUNT, tags).set(self.get_success_count())
        self.__reg.gauge(OVERSUBSCRIBE_RECLAIMED_CPU_COUNT, tags).set(self.get_reclaimed_cpu_count())
        self.__reg.gauge(OVERSUBSCRIBE_CONSUMED_CPU_COUNT, tags).set(self.get_consumed_cpu_count())

    def get_fail_count(self):
        return self.__fail_count

    def get_skip_count(self):
        return self.__skip_count

    def get_success_count(self):
        return self.__success_count

    def get_reclaimed_cpu_count(self):
        return self.__reclaimed_cpu_count

    def get_consumed_cpu_count(self):
        return self.__consumed_cpu_count

    def handle(self, event):
        if not self.__relevant(event):
            return

        self.handling_event(event, 'oversubscribing workloads')

        log.info('cleaning up old opportunistic resources')
        clean_count = self.__cleanup()
        log.info('cleaned up %d old opportunistic resources', clean_count)

        cpu_usage = self.__workload_monitor_manager.get_cpu_usage(seconds=3600, agg_granularity_secs=60)
        pred_env = PredEnvironment(self.__config_manager.get_region(), self.__config_manager.get_environment(),
                                   datetime.utcnow().hour)

        # Update consumed cpu metric and keep track of consumed cpu count to subtract from underutilized below
        consumed_cpu_count = 0
        for workload in self.workload_manager.get_workloads():
            if not workload.is_opportunistic():
                continue
            consumed_cpu_count += workload.get_opportunistic_thread_count()
        self.__consumed_cpu_count = consumed_cpu_count


        if self.__is_window_active():
            self.__skip_count += 1
            self.handled_event(event, 'skipping oversubscribe - a window is currently active')
            return


        workload_count = 0
        underutilized_cpu_count = 0
        consumed_cpu_count = 0
        # we calculate the window before we send the request to ensure we're not going over our 10 minute mark
        start = datetime.utcnow()
        end = start + timedelta(minutes=self.__config_manager.get_int(OVERSUBSCRIBE_WINDOW_SIZE_MINUTES_KEY,
                                                                      DEFAULT_OVERSUBSCRIBE_WINDOW_SIZE_MINUTES))
        for workload in self.workload_manager.get_workloads():
            log.debug('workload:%s job_type:%s cpu:%d', workload.get_app_name(), workload.get_job_type(),
                      workload.get_thread_count())

            if not self.__is_oversubscribable(workload, cpu_usage, pred_env):
                continue

            if workload.is_opportunistic():
                # only add the number of "real" threads (non-opportunistic)
                free = workload.get_thread_count() - workload.get_opportunistic_thread_count()
                if free <= 0:
                    continue
                underutilized_cpu_count += free
            else:
                underutilized_cpu_count += workload.get_thread_count()
            workload_count += 1

        free_cpu_count = underutilized_cpu_count - consumed_cpu_count
        if free_cpu_count > 0:
            self.__add_window(start, end, free_cpu_count)

        self.__success_count += 1
        self.__reclaimed_cpu_count = underutilized_cpu_count
        self.handled_event(event,
                           'oversubscribed {} cpus from {} workloads, {} total cpus are oversubscribed'.format(
                               free_cpu_count, workload_count, underutilized_cpu_count))

    def __relevant(self, event):
        if not event[ACTION] == OVERSUBSCRIBE:
            self.ignored_event(event, 'not a {} event'.format(OVERSUBSCRIBE))
            return False

        return True

    def __cleanup(self):
        try:
            oppo_list = self.__custom_api.list_namespaced_custom_object(version=OPPORTUNISTIC_RESOURCE_VERSION,
                                                                        group=OPPORTUNISTIC_RESOURCE_GROUP,
                                                                        plural=OPPORTUNISTIC_RESOURCE_PLURAL,
                                                                        namespace=OPPORTUNISTIC_RESOURCE_NAMESPACE)
            log.debug('cleanup: oppo list: %s', json.dumps(oppo_list))
            clean_count = 0
            check_secs = self.__config_manager.get_float(OVERSUBSCRIBE_CLEANUP_AFTER_SECONDS_KEY,
                                                         DEFAULT_OVERSUBSCRIBE_CLEANUP_AFTER_SECONDS)
            if check_secs <= 0:
                log.info('configured to skip cleanup. opportunistic resource windows will not be deleted.')
                return 0
            for item in oppo_list['items']:
                check_time = datetime.utcnow() + timedelta(seconds=-1*check_secs)
                if check_time < parse(item['spec']['window']['end']):
                    continue
                log.debug('deleting: %s', json.dumps(item))
                delete_opts = V1DeleteOptions(grace_period_seconds=0, propagation_policy='Foreground')
                resp = self.__custom_api.delete_namespaced_custom_object(version=OPPORTUNISTIC_RESOURCE_VERSION,
                                                                         group=OPPORTUNISTIC_RESOURCE_GROUP,
                                                                         plural=OPPORTUNISTIC_RESOURCE_PLURAL,
                                                                         namespace=OPPORTUNISTIC_RESOURCE_NAMESPACE,
                                                                         name=item['metadata']['name'],
                                                                         body=delete_opts)
                log.debug('deleted: %s', json.dumps(resp))
                clean_count += 1

            return clean_count
        except ApiException as e:
            log.error('Exception when calling CustomObjectsApi->list_namespaced_custom_object: %s', e)
            self.__fail_count += 1
            raise e

    def __is_oversubscribable(self, workload, cpu_usage, pred_env) -> bool:
        # as of right now we're only oversubscribing services
        # TODO expand to batch by checking predicted duration >>> 10m
        if workload.is_batch():
            return False

        pred = self.__cpu_usage_predictor_manager.get_predictor().predict(workload,
                                                                          cpu_usage.get(workload.get_id(), None),
                                                                          pred_env)
        if pred > self.__config_manager.get_float(TOTAL_THRESHOLD, DEFAULT_TOTAL_THRESHOLD):
            return False

        log.debug(' --> low utilization (%f), oversubscribing', pred)
        return True

    def __get_node(self):
        try:
            node = self.__core_api.read_node(self.__node_name)
            log.debug('node: %s', node)
            return node
        except ApiException as e:
            log.error('Exception when calling CoreV1Api->read_node: %s', e)
            self.__fail_count += 1
            raise e

    def __is_window_active(self):
        try:
            oppo_list = self.__custom_api.list_namespaced_custom_object(version=OPPORTUNISTIC_RESOURCE_VERSION,
                                                                        group=OPPORTUNISTIC_RESOURCE_GROUP,
                                                                        plural=OPPORTUNISTIC_RESOURCE_PLURAL,
                                                                        namespace=OPPORTUNISTIC_RESOURCE_NAMESPACE)
            log.debug('is active: oppo list: %s', json.dumps(oppo_list))
            for item in oppo_list['items']:
                log.debug('checking for window: %s', json.dumps(item))
                now = datetime.utcnow()
                if now < parse(item['spec']['window']['end']):
                    return True
            return False
        except ApiException as e:
            log.error('Exception when calling CustomObjectsApi->list_namespaced_custom_object: %s', e)
            self.__fail_count += 1
            raise e

    def __add_window(self, start, end, free_cpu_count):
        node = self.__get_node()
        log.debug('owner_kind:%s owner_name:%s owner_uid:%s', node.kind, node.metadata.name, node.metadata.uid)

        # add opportunistic resource
        try:
            oppo_meta = V1ObjectMeta(namespace=OPPORTUNISTIC_RESOURCE_NAMESPACE,
                                     name="{}-{}-{}".format(node.metadata.name, start.timestamp(), end.timestamp()),
                                     labels={
                                         'node_name': node.metadata.name,
                                         'node_uid': node.metadata.uid
                                     },
                                     owner_references=[
                                         V1OwnerReference(api_version=node.api_version,
                                                          kind=node.kind,
                                                          name=node.metadata.name,
                                                          uid=node.metadata.uid)
                                     ])
            oppo_spec = OpportunisticResourceSpec(capacity=OpportunisticResourceCapacity(free_cpu_count),
                                                  window=OpportunisticResourceWindow(start, end))
            oppo_body = OpportunisticResource(metadata=oppo_meta,
                                              spec=oppo_spec)
            oppo = self.__custom_api.create_namespaced_custom_object(version=OPPORTUNISTIC_RESOURCE_VERSION,
                                                                     group=OPPORTUNISTIC_RESOURCE_GROUP,
                                                                     plural=OPPORTUNISTIC_RESOURCE_PLURAL,
                                                                     namespace=OPPORTUNISTIC_RESOURCE_NAMESPACE,
                                                                     body=oppo_body)
            log.debug('created window: %s', json.dumps(oppo))
        except ApiException as e:
            log.error('Exception when calling CustomObjectsApi->create_namespaced_custom_object: %s', e)
            self.__fail_count += 1
            raise e

    # NOTE: this creates the CRD. should not be run and only really exists for testing purposes. example CRD:
    # {
    #     "apiVersion": "apiextensions.k8s.io/v1beta1",
    #     "kind": "CustomResourceDefinition",
    #     "metadata": {
    #         "creationTimestamp": "2019-08-13T23:23:00Z",
    #         "generation": 1,
    #         "name": "opportunistic-resources.titus.netflix.com",
    #         "resourceVersion": "472028",
    #         "selfLink": "/apis/apiextensions.k8s.io/v1beta1/customresourcedefinitions/opportunistic-resources.titus.netflix.com",
    #         "uid": "4a4afa45-be21-11e9-b347-120874de55a6"
    #     },
    #     "spec": {
    #         "conversion": {
    #             "strategy": "None"
    #         },
    #         "group": "titus.netflix.com",
    #         "names": {
    #             "kind": "OpportunisticResource",
    #             "listKind": "OpportunisticResourceList",
    #             "plural": "opportunistic-resources",
    #             "singular": "opportunistic-resource"
    #         },
    #         "scope": "Namespaced",
    #         "version": "v1",
    #         "versions": [
    #             {
    #                 "name": "v1",
    #                 "served": true,
    #                 "storage": true
    #             }
    #         ]
    #     },
    #     "status": {
    #         "acceptedNames": {
    #             "kind": "OpportunisticResource",
    #             "listKind": "OpportunisticResourceList",
    #             "plural": "opportunistic-resources",
    #             "singular": "opportunistic-resource"
    #         },
    #         "conditions": [
    #             {
    #                 "lastTransitionTime": "2019-08-13T23:23:00Z",
    #                 "message": "no conflicts found",
    #                 "reason": "NoConflicts",
    #                 "status": "True",
    #                 "type": "NamesAccepted"
    #             },
    #             {
    #                 "lastTransitionTime": null,
    #                 "message": "the initial names have been accepted",
    #                 "reason": "InitialNamesAccepted",
    #                 "status": "True",
    #                 "type": "Established"
    #             }
    #         ],
    #         "storedVersions": [
    #             "v1"
    #         ]
    #     }
    # }
    def __bootstrap(self):
        try:
            crd_list = self.__ext_api.list_custom_resource_definition(
                field_selector=OPPORTUNISTIC_RESOURCE_FIELD_SELECTOR)
            for item in crd_list.items:
                log.debug('CRD already exists: %s', item.to_str())
                return
        except ApiException as e:
            log.error('Exception when calling ApiextensionsV1beta1Api->list_custom_resource_definition: %s', e)

        crd_version = V1beta1CustomResourceDefinitionVersion(name=OPPORTUNISTIC_RESOURCE_VERSION,
                                                             served=True,
                                                             storage=True)
        crd_meta = V1ObjectMeta(name=OPPORTUNISTIC_RESOURCE_NAME)
        crd_spec_names = V1beta1CustomResourceDefinitionNames(kind=OPPORTUNISTIC_RESOURCE_KIND,
                                                              singular=OPPORTUNISTIC_RESOURCE_SINGULAR,
                                                              plural=OPPORTUNISTIC_RESOURCE_PLURAL)
        crd_spec = V1beta1CustomResourceDefinitionSpec(versions=[crd_version],
                                                       group=OPPORTUNISTIC_RESOURCE_GROUP,
                                                       names=crd_spec_names,
                                                       scope='Namespaced')
        crd = V1beta1CustomResourceDefinition(api_version=CRD_VERSION,
                                              kind=CRD_KIND,
                                              metadata=crd_meta,
                                              spec=crd_spec)
        try:
            crd_resp = self.__ext_api.create_custom_resource_definition(crd)
            log.debug('created CRD: %s', crd_resp.to_str())
        except ApiException as e:
            log.error('Exception when calling ApiextensionsV1beta1Api->create_custom_resource_definition: %s', e)