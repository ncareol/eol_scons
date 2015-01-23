# -*- python -*-

import os, os.path
import string
import SCons

_lrose_source_file = """
#include <toolsa/udatetime.h>
int main(int argc, char **argv)
{
    date_time_t now;
    time_t then = uunix_time(&now);
    return 0;
}
"""

def CheckLROSE(context):
    context.Message('Checking for lrose linking...')
    result = context.TryLink(_lrose_source_file, '.c')
    context.Result(result)
    return result

_settings = {}

lroseLibs = ['radar', 'rapmath', 'rapformats', 'Radx', 'Fmq', 
             'dsserver', 'didss', 'toolsa', 'dataport', 'Spdb']

def _calculate_settings(env, settings):
    prefix = '/usr/local/lrose'
    # Libs will be in <prefix>/lib
    libdir = os.path.join(prefix, 'lib')
    settings['LIBPATH'] = [ libdir ]
    # Headers will be in <prefix>/include
    headerdir = os.path.join(prefix, 'include')
    settings['CPPPATH'] = [ headerdir ]

    settings['LIBS'] = lroseLibs

    if env.GetOption('clean') or env.GetOption('help'):
        return

    clone = env.Clone()
    clone.Replace(LIBS=lroseLibs)
    clone.AppendUnique(CPPPATH=settings['CPPPATH'])
    clone.AppendUnique(LIBPATH=settings['LIBPATH'])
    conf = clone.Configure(custom_tests = { "CheckLROSE" : CheckLROSE })
    if not conf.CheckLROSE():
        msg = "Failed to link to LROSE. Check config.log."
        raise SCons.Errors.StopError, msg
    conf.Finish()

def generate(env):
    if not _settings:
        _calculate_settings(env, _settings)
    env.AppendUnique(CPPPATH=_settings['CPPPATH'])
    env.Append(LIBS=_settings['LIBS'])
    env.AppendUnique(LIBPATH=_settings['LIBPATH'])


def exists(env):
    return True
