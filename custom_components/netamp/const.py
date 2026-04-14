DOMAIN = "netamp"
DEFAULT_PORT = 9760
DEFAULT_SCAN_INTERVAL = 10  # seconds

CONF_SCAN_INTERVAL = "scan_interval"

ZONES = (1, 2)

# Response reading limits
MAX_RESPONSE_LINES = 64  # Maximum response lines before stopping
RESPONSE_IDLE_TIMEOUT = 0.25  # Idle timeout (seconds) between response lines

# Supported parameters we parse from responses
PARAM_SRC = "src"
PARAM_VOL = "vol"
PARAM_MUTE = "mute"   # legacy/typo-ish responses sometimes just say 'mute'
PARAM_MOFF = "moff"
PARAM_MXV = "mxv"
PARAM_BAS = "bas"
PARAM_TRE = "tre"
PARAM_BAL = "bal"
PARAM_ZNN = "znn"
PARAM_SN1 = "sn1"
PARAM_SN2 = "sn2"
PARAM_SN3 = "sn3"
PARAM_SN4 = "sn4"
PARAM_SNL = "snl"
PARAM_LIM = "lim"

# Value mapping
# Spec-defined selectable sources: 1, 2, 3, loc. Source "3a" (sn4) is a MAC-addressed
# network stream variant of source 3 and cannot be selected via a src command directly.
SRC_VALUES = ("1", "2", "3", "loc")
LIM_VALUES = {
    "1": "Auto",
    "a": "Analogue",
    "d": "Digital",
}
