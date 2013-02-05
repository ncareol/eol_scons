# Tool for xmlrpc-c Abyss server with C++ interface
# Docs for the API are available at http://xmlrpc-c.sourceforge.net/
import os
import SCons.Errors

def generate(env):
    # Use pkg-config to get C flags and libraries
    cmd = 'pkg-config --cflags --libs xmlrpc_server_abyss++'
    try:
        status = env.ParseConfig(cmd)
    except OSError as err:
        print "Error loading tool xmlrpc_server_abyss++:", err
        print "Have you installed package 'xmlrpc-c-devel' (or similar)?"
        raise SCons.Errors.StopError

def exists(env):
    status = os.system('pkg-config --exists xmlrpc_server_abyss++')
    return(status == 0)

