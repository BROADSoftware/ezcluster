

import os
import yaml
import logging
import imp

from misc import ERROR,appendPath


logger = logging.getLogger("ezcluster.modules")

class Module:
    def __init__(self, name, path):
        self.name = name
        self.path = path
        
    def getSchema(self):
        f = os.path.join(self.path, "schema.yml")
        if os.path.exists(f):
            return yaml.load(open(f))
        else:
            return {}
    
    def groom(self, model):
        codeFile = os.path.join(self.path, "groomer.py")
        if os.path.exists(codeFile):
            logger.debug("Will load '{0}' as python code".format(codeFile))
            groomer = imp.load_source(self.name, codeFile)
            method = getattr(groomer, "groom")
            if method != None:
                logger.debug("FOUND '{0}' method".format(str(groomer)))
                method(self, model)

    def walk(self, targetFileByName):
        """ Enrich the targetFileByName structure with file from this module """
        #logger.debug(self.path + "<----")
        snippetsPath = appendPath(self.path, "snippets")
        pref = len(snippetsPath) + 1
        for dirpath, dirnames, filenames in os.walk(snippetsPath):  # @UnusedVariable
            #logger.debug("dirpath:{}  dirnames:{}  filename:{}".format(dirpath, dirnames, filenames))
            for filename in filenames:
                #logger.debug(filename)
                if not filename == ".gitignore":
                    sourceFile = os.path.join(dirpath, filename)
                    targetFileName = sourceFile[pref:]
                    # Handle the type and eventual suffix (Used as short comment)
                    pos = targetFileName.rfind(".")
                    if pos == -1:
                        ERROR("'{0}' is not a valid file part".format(sourceFile))
                    suffix = targetFileName[pos+1:]
                    targetFileName = targetFileName[:pos]
                    pos = suffix.find("-")
                    if pos != -1:
                        ftype = suffix[:pos]
                        suffix = suffix[pos+1:]
                    else:
                        ftype = suffix
                        suffix = None
                    # Now order number
                    pos = targetFileName.rfind(".")
                    if pos == -1:
                        ERROR("'{0}' is not a valid file part".format(sourceFile))
                    idx = targetFileName[pos+1:]
                    targetFileName = targetFileName[:pos]
                    try:
                        order  = int(idx)
                    except ValueError:
                        ERROR("'{0}' is not a valid file part".format(sourceFile))
                        
                    logger.debug(sourceFile + "-->" + targetFileName + "(" + str(idx) + ")")
                    
                    if targetFileName not in targetFileByName:
                        targetFileByName[targetFileName] = {}
                        #targetFileByName[targetFileName].name = targetFileName
                        targetFileByName[targetFileName]['fileParts'] = []
                    fp = {}
                    fp['name'] = sourceFile
                    fp['order'] = order
                    fp['module'] = self.name
                    fp['type'] = ftype
                    if suffix != None:
                        fp["suffix"] = suffix
                    targetFileByName[targetFileName]['fileParts'].append(fp)
                    #targetFileByName[targetFileName].fileParts.insert(0, fp)   # To exercise the sort




def lookupModule(module, modulesPath):
    for path in modulesPath:
        p = os.path.join(path, module)
        if os.path.exists(p):
            return Module(module, p)
    ERROR("Unable to find module '{}'".format(module))
    

def buildModules(cluster, modulesPath):
    modules = []
    if "modules" in cluster:
        for m in cluster['modules']:
            modules.append(lookupModule(m, modulesPath))
    return modules

validType = set(["txt", "j2", "jj2"])
                
def buildTargetFileByName(modules):
    "Build a map by file name, where each file is an array of file parts"
    targetFileByName = {}
    for module in modules:
        module.walk(targetFileByName)
    # For each target file, sort parts by order. And check validity
    for name, targetFile in targetFileByName.iteritems():
        targetFile['fileParts'] = sorted(targetFile['fileParts'], key = lambda fp: fp['order'])
        refType = targetFile["fileParts"][0]['type']
        if refType not in validType:
            ERROR("Invalid type '{0}' for file '{1}'. (module:'{2}', target:'{3}'). Only {4} are allowed".format(refType, name, targetFile["fileParts"][0]['module'], targetFile["fileParts"][0]['name'], str(validType)))
        for fp in targetFile['fileParts']:
            if fp['type'] != refType:
                ERROR("Type mismatch for file target:'{0}' in module:'{1}'. All type for a target must be same ('{2}' != '{3}')".format(name, targetFile["fileParts"][0]['module'], fp['type'], refType))
    return targetFileByName
