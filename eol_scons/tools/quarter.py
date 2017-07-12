# -*- python -*-
import sys

def generate(env):
    env.Require('qt5')
    env.Require('coin')
    
    if sys.platform in ['linux', 'linux2']: 
        # There is no need to set specific include or library paths here.
        # It is enough to require the coin tool above, since Quarter
        # installs into the same location.  When built from source, both
        # install into the default configure prefix of /usr/local/.  When
        # installed as an RPM, Quarter headers are in /usr/include/Coin2
        # and the Quarter library is in the same place as the Coin library.
        env.AppendUnique(LIBS=['Quarter'])

    if sys.platform == 'darwin':
        qtframes = ['QtGui', 'QtCore', 'QtOpenGL']
    
        env.AppendUnique(FRAMEWORKS=['Inventor', 'Quarter']+qtframes)
        
        if 'QT5DIR' in env:
            qtframeworkdir = env['QT5DIR']+'/Frameworks'
        else:
            qtframeworkdir = '/usr/local/Frameworks'
            
        env.AppendUnique(FRAMEWORKPATH=['/Library/Frameworks', qtframeworkdir])
        
        # Add paths directly to the qt headers, because the Quarter code include
        # statements don't specify the framework name.
        for f in qtframes:
            framepath = qtframeworkdir+'/'+f+'.framework/Headers'
            env.AppendUnique(CPPPATH=[framepath])
    
    if sys.platform == 'win32':
        env.AppendUnique(CXXFLAGS=["-DCOIN_NOT_DLL","-DQUARTER_NOT_DLL"])
        env.AppendUnique(LIBS=["Quarter", "Coin"])

def exists(env):
    return True

