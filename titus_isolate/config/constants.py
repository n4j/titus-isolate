# Logs
LOG_FMT_STRING = '%(asctime)s,%(msecs)d %(levelname)s [%(filename)s:%(lineno)d] %(message)s'

# Metrics
DEFAULT_SAMPLE_FREQUENCY_SEC = 6

# Rebalance
REBALANCE_FREQUENCY_KEY = 'TITUS_ISOLATE_REBALANCE_FREQUENCY'
DEFAULT_REBALANCE_FREQUENCY = 18

# Reconcile
RECONCILE_FREQUENCY_KEY = 'TITUS_ISOLATE_RECONCILE_FREQUENCY'
DEFAULT_RECONCILE_FREQUENCY = 60

# CPU Allocator
CPU_ALLOCATOR = 'TITUS_ISOLATE_ALLOCATOR'
FALLBACK_ALLOCATOR = 'TITUS_ISOLATE_FALLBACK_ALLOCATOR'

# Remote Allocator
REMOTE_ALLOCATOR_URL = 'TITUS_ISOLATE_REMOTE_ALLOCATOR_URL'

AB_TEST = 'AB_TEST'
IP = 'IP'
FORECAST_CPU_IP = 'FORECAST_CPU_IP'
GREEDY = 'GREEDY'
NOOP = 'NOOP'
NOOP_RESET = 'NOOP_RESET'
REMOTE = 'REMOTE'
DEFAULT_ALLOCATOR = IP
DEFAULT_FALLBACK_ALLOCATOR = GREEDY
CPU_ALLOCATORS = [AB_TEST, IP, FORECAST_CPU_IP, GREEDY, NOOP, NOOP_RESET, REMOTE]

CPU_ALLOCATOR_A = 'CPU_ALLOCATOR_A'
CPU_ALLOCATOR_B = 'CPU_ALLOCATOR_B'

# Forecast CPU Allocator
ALPHA_NU = 'TITUS_ISOLATE_ALPHA_NU'
DEFAULT_ALPHA_NU = 1000.0

ALPHA_LLC = 'TITUS_ISOLATE_ALPHA_LLC'
DEFAULT_ALPHA_LLC = 10.0

ALPHA_L12 = 'TITUS_ISOLATE_ALPHA_L12'
DEFAULT_ALPHA_L12 = 250.0

ALPHA_ORDER = 'TITUS_ISOLATE_ALPHA_ORDER'
DEFAULT_ALPHA_ORDER = 1.0

ALPHA_PREV = 'TITUS_ISOLATE_ALPHA_PREV'
DEFAULT_ALPHA_PREV = 10.0

BURST_MULTIPLIER = 'TITUS_ISOLATE_BURST_MULTIPLIER'
DEFAULT_BURST_MULTIPLIER = 0.1

MAX_BURST_POOL_INCREASE_RATIO = 'TITUS_ISOLATE_MAX_BURST_POOL_INCREASE_RATIO'
DEFAULT_MAX_BURST_POOL_INCREASE_RATIO = 3.0

BURST_CORE_COLLOC_USAGE_THRESH = 'TITUS_ISOLATE_BURST_CORE_COLLOC_USAGE_THRESH'
DEFAULT_BURST_CORE_COLLOC_USAGE_THRESH = 0.2

WEIGHT_CPU_USE_BURST = 'TITUS_ISOLATE_WEIGHT_CPU_USE_BURST'
DEFAULT_WEIGHT_CPU_USE_BURST = 1.0

RELATIVE_MIP_GAP_STOP = 'TITUS_RELATIVE_MIP_GAP_STOP'
DEFAULT_RELATIVE_MIP_GAP_STOP = 0.05

MIP_SOLVER = 'TITUS_ISOLATE_MIP_SOLVER'
DEFAULT_MIP_SOLVER = 'GLPK_MI'

# Free Thread Provider
FREE_THREAD_PROVIDER = 'FREE_THREAD_PROVIDER'
EMPTY = 'EMPTY'
THRESHOLD = 'THRESHOLD'
DEFAULT_FREE_THREAD_PROVIDER = EMPTY

# Threshold Free Thread Provider
TOTAL_THRESHOLD = 'TOTAL_THRESHOLD'
DEFAULT_TOTAL_THRESHOLD = 0.1

THRESHOLD_TOTAL_DURATION_SEC = 'THRESHOLD_TOTAL_DURATION_SEC'
DEFAULT_THRESHOLD_TOTAL_DURATION_SEC = 600

PER_WORKLOAD_THRESHOLD = 'PER_WORKLOAD_THRESHOLD'
DEFAULT_PER_WORKLOAD_THRESHOLD = 0.05

PER_WORKLOAD_DURATION_SEC = 'PER_WORKLOAD_DURATION_SEC'
DEFAULT_PER_WORKLOAD_DURATION_SEC = DEFAULT_SAMPLE_FREQUENCY_SEC

# cgroup File
WAIT_CGROUP_FILE_KEY = 'TITUS_ISOLATE_WAIT_CGROUP_FILE_SEC'
DEFAULT_WAIT_CGROUP_FILE_SEC = 90

# JSON File
WAIT_JSON_FILE_KEY = 'TITUS_ISOLATE_WAIT_JSON_FILE_SEC'
DEFAULT_WAIT_JSON_FILE_SEC = 10

# Blocking isolation wait
TITUS_ISOLATE_BLOCK_SEC = 'TITUS_ISOLATE_BLOCK_SEC'
DEFAULT_TITUS_ISOLATE_BLOCK_SEC = 10

# NUMA balancing
TITUS_ISOLATE_DYNAMIC_NUMA_BALANCING = 'TITUS_ISOLATE_DYNAMIC_NUMA_BALANCING'
DEFAULT_TITUS_ISOLATE_DYNAMIC_NUMA_BALANCING = True

# Event log
EVENT_LOG_FORMAT_STR = 'EVENT_LOG_FORMAT_STR'

# S3 Buckets
DEV = 'prod'
V1 = 'v1'
LATEST = 'latest'

MODEL_BUCKET_FORMAT_STR = 'TITUS_ISOLATE_MODEL_BUCKET_FORMAT_STR'
MODEL_PREFIX_FORMAT_STR = 'TITUS_ISOLATE_MODEL_PREFIX_FORMAT_STR'

MODEL_BUCKET_PREFIX = 'TITUS_ISOLATE_MODEL_BUCKET_PREFIX'
DEFAULT_MODEL_BUCKET_PREFIX = DEV

MODEL_BUCKET_LEAF = 'TITUS_ISOLATE_MODEL_BUCKET_LEAF'
DEFAULT_MODEL_BUCKET_LEAF = LATEST

# Static environment variables
PROPERTY_URL_ROOT = 'http://localhost:3002/properties'
EC2_INSTANCE_ID = "EC2_INSTANCE_ID"

MAX_SOLVER_RUNTIME = 'TITUS_ISOLATE_MAX_SOLVER_RUNTIME'
DEFAULT_MAX_SOLVER_RUNTIME = 1

RESTART_PROPERTIES = [
    ALPHA_NU,
    ALPHA_LLC,
    ALPHA_L12,
    ALPHA_ORDER,
    ALPHA_PREV,
    BURST_CORE_COLLOC_USAGE_THRESH,
    BURST_MULTIPLIER,
    CPU_ALLOCATOR,
    FALLBACK_ALLOCATOR,
    FREE_THREAD_PROVIDER,
    MAX_BURST_POOL_INCREASE_RATIO,
    MAX_SOLVER_RUNTIME,
    MODEL_BUCKET_FORMAT_STR,
    MODEL_PREFIX_FORMAT_STR,
    PER_WORKLOAD_DURATION_SEC,
    PER_WORKLOAD_THRESHOLD,
    REBALANCE_FREQUENCY_KEY,
    RECONCILE_FREQUENCY_KEY,
    REMOTE_ALLOCATOR_URL,
    THRESHOLD_TOTAL_DURATION_SEC,
    TOTAL_THRESHOLD,
    WEIGHT_CPU_USE_BURST]
