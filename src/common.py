import configparser, logging, logging.handlers, os, sys

def xstr(s):
    return '' if s is None else str(s)

# -----------------------------------------------------------------------------
# Config file handling
# -----------------------------------------------------------------------------

# Get the config from specified filename
def readConfig(fname):
    config = configparser.ConfigParser()
    with open(fname) as f:
        config.read_file(f)
    return config['DEFAULT']

def baseProgName():
    return os.path.basename(sys.argv[0])

def configFileName():
    return os.path.splitext(baseProgName())[0] + '.ini'

# -----------------------------------------------------------------------------
# Log handling
# -----------------------------------------------------------------------------

# Log info on mail that is processed. Logging now rotates at midnight (as per the machine's locale)
def createLogger(logfile, logfileBackupCount):
    # No longer using basicConfig, as it echoes to stdout, and logging all done in main thread now
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    fh = logging.handlers.TimedRotatingFileHandler(logfile, when='midnight', backupCount=logfileBackupCount)
    formatter = logging.Formatter('%(asctime)s,%(name)s,%(levelname)s,%(message)s')
    fh.setFormatter(formatter)
    logger.addHandler(fh)
    return logger