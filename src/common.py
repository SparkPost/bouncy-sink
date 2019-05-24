import configparser

# Get the config from specified filename
def readConfig(fname):
    config = configparser.ConfigParser()
    with open(fname) as f:
        config.read_file(f)
    return config['DEFAULT']
