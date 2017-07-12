"""
SCons.Tool.osxqtapp

Create an OSX application bundle from a qt executable.

See OsxQtApp() for the parameter descriptions.

Example:
  switchappname = 'RICSwitch-' + apprevision
  switchappdir = Dir(switchappname+'.app')
  switchapp = env.OsxQtApp(switchappdir, 
                           '#/switch/ric_switch', 
                           '#/Resources/proxy/proxyIcon.icns', 
                           switchappname, 
                           apprevision)

Process:
 - Remove the existing bundle, if present.
 - Populate the bundle directory tree with the executable and icon files.
 - create Info.plist and copy to Contents/
 - create the launch_app script and copy to Contents/
 - run macdeployqt on the bundle, which copies in needed frameworks and libraries.
 
Info.plist is an XML description of the application.

The bundle hierarchy is as follows:
apname.app/
   Contents/
      Frameworks/
         frameworks and libraries
      MacOS/
         executable
         launch_app
      Resources/
         icon file
      Info.plist

"""

import os
import subprocess

from SCons.Script import *

class ToolOsxQtAppWarning(SCons.Warnings.Warning):
    pass

class MacdeployqtNotFound(ToolOsxQtAppWarning):
    pass

class NotAnOsxSystem(ToolOsxQtAppWarning):
    pass

SCons.Warnings.enableWarningClass(ToolOsxQtAppWarning)


def _make_info_plist(bundle_name, bundle_identifier, bundle_signature, bundle_version, icon_filename):
    """
    Return a customized Info.plist. This is a manifest that is found in Contents/ in the bundle.
    
    Parameters:
		Should be self evident       
    """
    
    
    bundleName        = bundle_name
    bundleDisplayName = bundle_name
    bundleIdentifier  = bundle_identifier
    bundleVersion     = bundle_version
    bundleSignature   = bundle_signature
    bundleIconFile    = icon_filename
    
    info = r"""
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
	<key>CFBundleName</key>
	<string>%s</string>
	<key>CFBundleDisplayName</key>
	<string>%s</string>
	<key>CFBundleIdentifier</key>
	<string>%s</string>
	<key>CFBundleVersion</key>
	<string>%s</string>
	<key>CFBundlePackageType</key>
	<string>APPL</string>
	<key>CFBundleSignature</key>
	<string>%s</string>
	<key>CFBundleExecutable</key>
	<string>launch_app</string>
	<key>CFBundleIconFile</key>
	<string>%s</string>
</dict>
</plist>
    """ %(
        bundleName, 
        bundleDisplayName,
        bundleIdentifier, 
        bundleVersion, 
        bundleSignature, 
        bundleIconFile
    )
    
    return info
    
def _make_launch_app(appexe_filename):
    """
    Create the text for a script which sets DYLD_LIBRARY_PATH and DYLD_FRAMEWORK_PATH
    and then exec's the program
    
    Parameters:
    appexe_filename -- The executable name, which will be found in Contents/MacOS
    """

    script = r"""#!/bin/sh

# Locate important directories 
DIR=$(cd "$(dirname "$0")"; pwd)
TOPDIR=$DIR/..
RESDIR=$TOPDIR/Resources
FRAMEDIR=$TOPDIR/Frameworks

# Set the locations for frameworks and libraries
export DYLD_LIBRARY_PATH="$FRAMEDIR:$DIR:$RESDIR"
export DYLD_FRAMEWORK_PATH="$FRAMEDIR"
env | grep DYLD

# Run the app
exec $DIR/%s
    """ % (str(appexe_filename))

    # Return the text of the customized script
    return script
    
def _find_mdqt(env):
    """ 
    Look for macdeployqt.
    
    Returns the path to the executable, if found. Otherwise
    raises an error exception.
    """
    try: 
        return env['MACDEPLOYQT']
    except KeyError: 
        pass

    macdeployqt = env.WhereIs('macdeployqt')
    if macdeployqt:
        return macdeployqt

    raise SCons.Errors.StopError(
        MacdeployqtNotFound,
        "Could not find macdeployqt")
    return None

#
# Builder to run macdeployqt on a bundle
#
def _macdeployqt(target, source, env):
    """
    Run macdepoyqt on the bundle.
    
    Parameters:
    target[0] -- bogus
    
    source[0] -- The bundle directory, e.g. RICProxy-6454.app.
    
    env['EXENAME']    -- e.g. ric_proxy
    
    Since macdeployqt requires the bundle to have the same name as the executable
    inside of it, the bundle directory is first renamed, macdeployqt is applied,
    and then the bundle is renamed to the original.
    """
    bundle = source[0]
    exename = env['EXENAME']
    
    d = os.path.dirname(str(bundle))
    tmpbundle = d + '/' + exename + '.app'
    
    # Get rid of the temporary bundle, if it has been left lying around
    Execute(Delete(tmpbundle))
    
    # Move the existing bundle
    Execute(Move(tmpbundle, bundle))
    
    # Run macdeployqt
    # For some reason, I couldn't get Execute(Command)) to work, so
    # fall back to using subprocess.
    subprocess.check_call("env['MACDEPLOYQT'] tmpbundle -verbose=2", stderr=subprocess.STDOUT, bufsize=1)
    
    # Move temporary bundle back
    Execute(Move(bundle, tmpbundle))
    
#
# Builder to create a bundle.
#
def _create_bundle(target, source, env):
    """
    Create and populate an OSX application bundle.
    
    Parameters:
    target[0] -- The bundle directory
    
    source[0] -- The application executable file, e.g. #/proxy/ric_proxy.
    source[1] -- The application icon file, e.g. #/Resources/proxy/proxyIcons.icns.
    
    Environment values:
    env['APPNAME']    -- The final application bundle name, e.g. RICProxy-5467M
    env['APPVERSION'] -- The version number to be included in the manifest, e.g. 5467M
    """
    
    appname      = env['APPNAME']
    appversion   = env['APPVERSION']
    exename      = os.path.basename(str(source[0]))
    iconname     = os.path.basename(str(source[1]))
    bundle       = target[0]
    bundledir    = bundle.get_abspath()
    contentsdir  = Dir(bundledir + '/Contents')
    macosdir     = Dir(bundledir + '/Contents/MacOS')
    resourcesdir = Dir(bundledir + '/Contents/Resources')

    # Get rid of the existing bundle. Otherwise macdeployqt gets bent out of shape 
    # when it finds its products already there.
    Execute(Delete(bundle))

    # Buid the basic bundle structure
    Execute(Mkdir(bundledir))    
    Execute(Mkdir(contentsdir))    
    Execute(Mkdir(macosdir))    
    Execute(Mkdir(resourcesdir))    
     
    # Copy the executable and icon
    Execute(Copy(macosdir, source[0]))
    Execute(Copy(resourcesdir, source[1]))
            
    # Create Info.plist in the Contents/ directory
    info =  _make_info_plist(
        bundle_name=appname, 
        bundle_identifier=exename, 
        bundle_signature='ncar-eol-cds-qt-app', 
        bundle_version=appversion, 
        icon_filename=iconname)
    infofilepath = contentsdir.get_abspath() + '/Info.plist'
    infoplistfile = file(infofilepath,"w")
    infoplistfile.write(info)
    
    # Create launch_app script in the MacOS directory.
    scripttext = _make_launch_app(exename)
    filepath = macosdir.get_abspath() + '/launch_app'
    launchappfile = file(filepath,"w")
    launchappfile.write(scripttext)
    os.chmod(filepath, 0775)
        
def OsxQtApp(env, destdir, appexe, appicon, appname, appversion, *args, **kw):
    """
    A pseudo-builder to create an OSX application bundle for a Qt application.
    
    An OSX application bundle hierarchy is created, and the executable and 
    other artifacts are copied in. The macdeployqt application is run on
    the bundle in order to bring in supporting frameworks and libraries.
    
    A script (launch_app) is created which sets environment values such as
    DYLD_LIBRARY_PATH and DYLD_FRAMEWORK_PATH to the locations within
    the bundle, and then runs the application. This script is designated as
    the application executable in the Info.plist file.
    
    The final bundle name will be appname + '.app'. 
    
    Parameters:
    destdir    -- The directory where the bundle will be created. Must end with '.app'
    appexe     -- The path to the application executable.
    appicon    -- The path to the application icon.
    appname    -- The final name of the app, without '.app'. E.g. 'Proxy-6457'
    appversion -- The version number to be included in Info.plist
    
    """
    
    # Establish some useful attributes.
    exename    = str(os.path.basename(appexe))
    bundledir  = Dir(str(destdir))
    exe        = File(str(bundledir) + '/Contents/MacOS/' + exename)
    icon       = File(str(bundledir) + '/Contents/Resources/' + str(os.path.basename(appicon)))
    info       = File(str(bundledir) + '/Contents/Info.plist')

    # Create the bundle.
    bundle = env.MakeBundle(bundledir,  [appexe, appicon], APPNAME=appname, APPVERSION=appversion)
    env.AlwaysBuild(bundle)
    env.Clean(bundle, bundle)

    # Run macdeployqt on the bundle. 
    bogustarget = str(bundledir) + '_bogus'
    mdqt = env.MacDeployQt(bogustarget, bundle, EXENAME=exename)
    env.AlwaysBuild(mdqt)

    return mdqt
    
def generate(env):
    """Add Builders and construction variables to the Environment."""

    # Define the bundle builder. It takes the executable and other aritifacts
    # as sources, and populates a new bundle hierarchy.
    bldr = Builder(action = _create_bundle);
    env.Append(BUILDERS = {'MakeBundle' : bldr})
    
    # Define the macqtdeploy builder. It takes a bundle directory
    # as a source, and runs macdeployqt on it.
    mdqt = Builder(action = _macdeployqt)
    env.Append(BUILDERS = {'MacDeployQt' : mdqt})
    
    # find macdeployqt command
    env['MACDEPLOYQT'] = _find_mdqt(env)

    # Define the important method.
    env.AddMethod(OsxQtApp, "OsxQtApp")

def exists(env):
    if (sys.platform != 'darwin'):
        raise SCons.Errors.StopError(
            NotAnOsxSystem,
            "Trying to create an application bundle on a non-OSX system")
        return None

    return _find_mdqt(env) 
    
