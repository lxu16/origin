"""
API for preview namelist
"""

from CIME.XML.standard_module_setup import *

import glob, shutil, imp
logger = logging.getLogger(__name__)

def create_dirs(case):
    """
    Make necessary directories for case
    """
    # Get data from XML
    exeroot = case.get_value("EXEROOT")
    libroot = case.get_value("LIBROOT")
    incroot = case.get_value("INCROOT")
    rundir = case.get_value("RUNDIR")
    caseroot = case.get_value("CASEROOT")


    docdir = os.path.join(caseroot, "CaseDocs")
    dirs_to_make = []
    models = case.get_values("COMP_CLASSES")
    for model in models:
        dirname = "cpl" if model == "DRV" else model.lower()
        dirs_to_make.append(os.path.join(exeroot, dirname, "obj"))

    dirs_to_make.extend([exeroot, libroot, incroot, rundir, docdir])

    for dir_to_make in dirs_to_make:
        if (not os.path.isdir(dir_to_make)):
            try:
                logger.debug("Making dir '%s'" % dir_to_make)
                os.makedirs(dir_to_make)
            except OSError as e:
                expect(False, "Could not make directory '%s', error: %s" % (dir_to_make, e))

    # As a convenience write the location of the case directory in the bld and run directories
    for dir_ in (exeroot, rundir):
        with open(os.path.join(dir_,"CASEROOT"),"w+") as fd:
            fd.write(caseroot+"\n")

def create_namelists(case):

    case.flush()

    casebuild = case.get_value("CASEBUILD")
    caseroot = case.get_value("CASEROOT")
    rundir = case.get_value("RUNDIR")

    docdir = os.path.join(caseroot, "CaseDocs")

    # Load modules
    case.load_env()

    # Create namelists - must have DRV last in the list below
    # Note - DRV must be last in the loop below so that in generating its namelist, 
    # it can use xml vars potentially set by other component's buildnml scripts
    models = case.get_values("COMP_CLASSES")
    models_reverse = models[::-1]
    for model in models_reverse:
        model_str = model.lower()
        config_file = case.get_value("CONFIG_%s_FILE" % model_str.upper())
        config_dir = os.path.dirname(config_file)
        if model_str == "drv":
            compname = "drv"
        else:
            compname = case.get_value("COMP_%s" % model_str.upper())
        cmd = os.path.join(config_dir, "buildnml")
        try:
            mod = imp.load_source("buildnml", cmd)
            logger.info("Calling %s buildnml"%compname)
            mod.buildnml(case, caseroot, compname)

        except SyntaxError as detail:
            with open(cmd, 'r') as f:
                first_line = f.readline()
            if 'python' in first_line:
                expect(False, detail)
            else:
                run_cmd_no_fail("%s %s" % (cmd, caseroot), verbose=True)
        except AttributeError:
            run_cmd_no_fail("%s %s" % (cmd, caseroot), verbose=True)
        except:
            raise

    # refresh case xml object from file
    case.read_xml()

    # Save namelists to docdir
    if (not os.path.isdir(docdir)):
        os.makedirs(docdir)
        try:
            with open(os.path.join(docdir, "README"), "w") as fd:
                fd.write(" CESM Resolved Namelist Files\n   For documentation only DO NOT MODIFY\n")
        except (OSError, IOError) as e:
            expect(False, "Failed to write %s/README: %s" % (docdir, e))


    for cpglob in ["*_in_[0-9]*", "*modelio*", "*_in",
                   "*streams*txt*", "*stxt", "*maps.rc", "*cism.config*"]:
        for file_to_copy in glob.glob(os.path.join(rundir, cpglob)):
            logger.debug("Copy file from '%s' to '%s'" % (file_to_copy, docdir))
            shutil.copy2(file_to_copy, docdir)

    # Copy over chemistry mechanism docs if they exist
    if (os.path.isdir(os.path.join(casebuild, "camconf"))):
        for file_to_copy in glob.glob(os.path.join(casebuild, "camconf", "*chem_mech*")):
            shutil.copy2(file_to_copy, docdir)
