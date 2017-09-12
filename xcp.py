#!/usr/bin/python

###
### Main module
###

import XenAPI
import MySQLdb
import sys

try:
    import sqlite as sqlite3
except ImportError, e:
    import sqlite3

try:
    xcplab = __import__(sys.argv[1])
except IndexError, e:
    print "Usage: %s <config>" % sys.argv[0]
    sys.exit()
except ImportError, e:
    print "Could not load %s.py config file" % sys.argv[1]
    sys.exit()
import xcpconf

def findNet(xapi, strNet):
    return xapi.network.get_by_name_label(strNet)


def findTemplate(xapi, strTemplate):
    objVMs = findVM(xapi, strTemplate)
    if objVMs:
        if xapi.VM.get_is_a_template(objVMs[0]):
            return objVMs[0]
        else:
            print "VM by name: " + strTemplate + " is not template"
    return None


def findVM(xapi, strVM):
    return xapi.VM.get_by_name_label(strVM)


def deleteVM(xapi, strVM):
    objVM = findVM(xapi, strVM)
    if not objVM:
        print "VM: " + strVM + " not found. VM not delete!"
        return False
    objVMs = xapi.VM.get_all_records()
    if config['debug']:
        print "Check power state"
    pwrState = objVMs[objVM[0]]["power_state"].lower()
    if 'halted' not in pwrState:
        xapi.VM.hard_shutdown(objVM[0])
    if config['debug']:
        print "Delete VDIs VM: " + strVM
    objVBDs = xapi.VBD.get_all_records()
    cfgVBDs = objVMs[objVM[0]]["VBDs"]
    for objVBD in cfgVBDs:
        record = objVBDs[objVBD]
        if 'CD' not in record["type"]:
            xapi.VDI.destroy(record["VDI"])
    xapi.VM.destroy(objVM[0])
    return


def createVM(xapi, strUser, cfgVM, objForVM, configLab):
    strVM = strUser + cfgVM['suffix']

    if config['debug']:
        print "Clone template: " + configLab['templates'][cfgVM['template']] + " to vm: " + strVM
    objVM = xapi.VM.clone(objForVM['templates'][cfgVM['template']], strVM)
    if not objVM:
        print "Template: " + configLab['templates'][cfgVM['template']] + " not clone to vm: " + strVM
        return False
    if config['debug']:
        print "Delete VIFs cloned VM"
    objVIFs = xapi.VIF.get_all_records()
    for objVIF in objVIFs:
        record = objVIFs[objVIF]
        if record["VM"] == objVM:
            xapi.VIF.destroy(objVIF)
    if config['debug']:
        print "Create VIF for vm: " + strVM
    for network in cfgVM['networks']:
        cfgVIF = {
        'device': '0',
        'network': objForVM['networks'][network],
        'VM': objVM,
        'MAC': "",
        'MTU': "1500",
        'qos_algorithm_type': "",
        'qos_algorithm_params': {},
        'other_config': {}
        }
        objVIF = xapi.VIF.create(cfgVIF)
        if not objVIF:
            print "VIF not create for vm: " + strVM
            xapi.VM.destroy(objVM)
            return False
    if config['debug']:
        print "Set tags for vm: " + strVM
    cfgTags = []
    for tag in cfgVM['tags']:
        cfgTags.append(configLab['tags'][tag])
    xapi.VM.set_tags(objVM, cfgTags)
    cfgOtherConfig = xapi.VM.get_other_config(objVM)
    cfgOtherConfig['folder'] = configLab['folders'][cfgVM['folder']]
    xapi.VM.set_other_config(objVM, cfgOtherConfig)
    if config['debug']:
        print "Provision vm: " + strVM
    xapi.VM.provision(objVM)
    return objVM


def deleteRightsXVP(sqlCur, strUser, strVM, configLab):
    if config['debug']:
        print "Delete row where VM: " + strVM + ", user: " + strUser
    sqlCur.execute("""
		delete from xvp_users
		where username = %s
		and vmname = %s""", (strUser + "@" + configLab['domainKrb'], strVM,))
    if config['debug']:
        print "Result exec SQL:"
        print sqlCur.rowcount
    sqlCur.execute("""
		select * from xvp_users
		where username = %s
		and rights != %s""", (strUser + "@" + configLab['domainKrb'], 'none',))
    if config['debug']:
        print "Result exec SQL:"
        print sqlCur.rowcount
    if len(sqlCur.fetchall()) == 0:
        sqlCur.execute("""
			delete from xvp_users
			where username = %s""", (strUser + "@" + configLab['domainKrb'],))
        if config['debug']:
            print "Result exec SQL:"
            print sqlCur.rowcount
    return True


def createRightsXVP(sqlCur, strUser, strVM, config, configLab):
    strUser = strUser.lower()

    sqlCur.execute("""
		select * from xvp_users
		where username = %s
		and vmname = %s""", (strUser + "@" + configLab['domainKrb'], strVM))
    if config['debug']:
        print "Result exec SQL exist Rights: "
        print sqlCur.rowcount
    if len(sqlCur.fetchall()) == 0:
        if config['debug']:
            print "Insert row where VM: " + strVM + ", user: " + strUser
        sqlCur.execute("""
			insert into xvp_users
			values (%s, %s, %s, %s, %s)""",
            (strUser + "@" + configLab['domainKrb'], configLab['poolName'], '*', strVM, 'all',))
        if config['debug']:
            print "Result exec SQL insert 'all' rights:"
            print sqlCur.rowcount

    sqlCur.execute("""
		select * from xvp_users
		where username = %s
		and rights = %s""", (strUser + "@" + configLab['domainKrb'], 'none',))
    if config['debug']:
        print "Result exec SQL found 'none' rights: "
        print sqlCur.rowcount
    if len(sqlCur.fetchall()) == 0:
        sqlCur.execute("""
			insert into xvp_users
			values (%s, %s, %s, %s, %s)""",
            (strUser + "@" + configLab['domainKrb'], configLab['poolName'], '-', '-', 'none'))
        if config['debug']:
            print "Result exec SQL add 'none' rights:"
            print sqlCur.rowcount
    return True


def addTrainerRightsXVP(sqlCur, strUser, config, configLab):
    strUser = strUser.lower()

    # get all tags start with 'group ' and remove 'group ' from them
    tags = [val[6:] for val in configLab['tags'].values() if 'group ' in val]
    if len(tags) == 0:
        print "groups not found!"
        return None

    if config['debug']:
        print "set trainer " + strUser + "@" + configLab['domainKrb'] + " for courses: " + ', '.join(tags)
        print tags

    for tag in tags:
        sqlCur.execute("""
        select * from xvp_users
        where groupname = %s
        and vmname = %s
        and username = %s
        """, (tag, "'*'", strUser + "@" + configLab['domainKrb']))

        if config['debug']:
            print "tag " + tag + " exist:"
            print sqlCur.rowcount

        if len(sqlCur.fetchall()) == 0:
            sqlCur.execute("""
                insert into xvp_users
                values (%s, %s, %s, %s, %s)
                """, (strUser + "@" + configLab['domainKrb'], configLab['poolName'], tag, '*', 'all'))
            if config['debug']:
                print "trainer for " + tag + " added:"
                print sqlCur.rowcount

    # add trainer's "none" rights
    sqlCur.execute("""
    		select * from xvp_users
    		where username = %s
    		and rights = %s""", (strUser + "@" + configLab['domainKrb'], 'none',))
    if config['debug']:
        print "Result exec SQL found 'none' rights: "
        print sqlCur.rowcount
    if len(sqlCur.fetchall()) == 0:
        sqlCur.execute("""
    			insert into xvp_users
    			values (%s, %s, %s, %s, %s)""",
                       (strUser + "@" + configLab['domainKrb'], configLab['poolName'], '-', '-', 'none'))
        if config['debug']:
            print "Result exec SQL add 'none' rights:"
            print sqlCur.rowcount
    return True


def createLab(xapi, sqlCur, configLab, config):
    if config['debug']:
        print "Collect object for VM"
    ##
    ## Find objects for VM
    ##
    objForVM = {}

    #
    # Find nets:
    #
    if config['debug']:
        print "Find networks"

    objForVM['networks'] = {}

    for key, val in configLab['networks'].iteritems():
        if config['debug']:
            print "*%s*" % val
        nets = findNet(xapi, val)
        print nets
        if nets:
            objForVM['networks'][key] = nets[0]
            if config['debug']:
                print "Find network: " + objForVM['networks'][key]
        else:
            print "Networks not found"
            sys.exit(1)

    #
    # Find templates:
    #
    if config['debug']:
        print "Find templates"

    objForVM['templates'] = {}

    for key, val in configLab['templates'].iteritems():
        template = findTemplate(xapi, val)
        if template:
            objForVM['templates'][key] = template
            if config['debug']:
                print "Find template: " + objForVM['templates'][key]
        else:
            print "Templates not found"
            sys.exit(1)

    if config['debug']:
        print "Create lab objects"

    ##
    ## Set trainer
    ##

    if configLab['trainer']:
        if config['debug']:
            print "adding trainer " + configLab['trainer']
        res = addTrainerRightsXVP(sqlCur, configLab['trainer'], config, configLab)
        if not res:
            print "trainer not created!"


    ##
    ## Create lab
    ##

    for strUser in configLab['users']:
        for cfgVM in configLab['vms']:
            strVM = strUser + cfgVM['suffix']
            if config['debug']:
                print "Check vm:" + strVM + " to exist"
            objVMs = findVM(xapi, strUser + cfgVM['suffix'])
            if objVMs:
                print "VM: " + strVM + " found. This VM not create!!!"
                print objVMs
                res = createRightsXVP(sqlCur, strUser, xapi.VM.get_uuid(objVMs[0]), config, configLab)
                if not res:
                    print "rights for vm: " + strVM + " on the user: " + strUser + " Not create!!!"

                continue
            if config['debug']:
                print "Create vm: " + strVM
            ref = createVM(xapi, strUser, cfgVM, objForVM, configLab)
            if not ref:
                print "VM: " + strVM + " Not create!!!"
                sys.exit(1)
            if config['debug']:
                print "VM: " + strVM + " Created!"
                print "Create rights for vm: " + strVM
            res = createRightsXVP(sqlCur, strUser, xapi.VM.get_uuid(ref), config, configLab)
            if not res:
                print "rights for vm: " + strVM + " on the user: " + strUser + " Not create!!!"
                sys.exit(1)
            if config['debug']:
                print "rights for VM: " + strVM + " on the user: " + strUser + " Created!"

    return


def deleteLab(xapi, sqlCur, configLab):
    ##
    ## Create lab
    ##

    for strUser in configLab['users']:
        for cfgVM in configLab['vms']:
            strVM = strUser + cfgVM['suffix']
            if config['debug']:
                print "Check vm:" + strVM + " to exist"
            objVMs = findVM(xapi, strUser + cfgVM['suffix'])
            if not objVMs:
                print "VM: " + strVM + " not found. This VM not deleted!!!"
                continue
            if config['debug']:
                print "Delete vm: " + strVM
            deleteVM(xapi, strVM)
            if config['debug']:
                print "VM: " + strVM + " Deleted!"
                print "Delete rights for vm: " + strVM
            res = deleteRightsXVP(sqlCur, strUser, strVM, configLab)
            if not res:
                print "Rights for vm: " + strVM + " on the user: " + strUser + " Not deleted!!!"
                sys.exit(1)
            if config['debug']:
                print "Rights for VM: " + strVM + " on the user: " + strUser + " deleted!"

    return


def deleteOddRows(xapi, sqlCur):
    ##
    ## Delete all rows from database with VM UUIDs that are not in pool now
    ##

    ## Get all VM UUIDs from pool
    #
    xVMs = xapi.VM.get_all_records().items()

    #save special rights as '-' and '*'
    poolIDs = ['-', '*']
    for opaque_ref, vm in xVMs:
        poolIDs.append(vm["uuid"])
    #

    ## Get all UUIDs from database
    #
    sqlCur.execute("select vmname from xvpusers.xvp_users")
    sqlIDs = [i[0] for i in list(sqlCur)]
    #

    ## Convert to string
    #
    if isinstance(sqlIDs[1], unicode):
        sqlIDs = [x.encode('UTF8') for x in sqlIDs]
    if isinstance(poolIDs[1], unicode):
        poolIDs = [x.encode('UTF8') for x in poolIDs]

    if config['debug']:
        print 'sqlIDs length: ', len(sqlIDs)
        print 'poolIDs length: ', len(poolIDs)
    #

    ## Get all odd IDs that are in database but bot in pool and delete them from db
    #
    oddIDs = [x for x in sqlIDs if x not in poolIDs]
    if config['debug']:
        print 'oddIDs', oddIDs

    if len(oddIDs) == 0:
        if config['debug']:
            print 'Nothing to delete'
        return

    format_strings = ','.join(['%s'] * len(oddIDs))
    sqlCur.execute("delete from xvpusers.xvp_users where vmname in (%s)" % format_strings, tuple(oddIDs))
    #

    return


configLab = xcplab.configLab
config = xcpconf.config

if config['SQLEngine'] == "SQLite":
    if config['debug']:
        print "Connect to sqlite db: " + config['SQLiteBase']

    SQLConnect = sqlite3.connect(config['SQLiteBase'])
    SQLConnect.isolation_level = None
    SQLCursor = SQLConnect.cursor()

elif config['SQLEngine'] == "MySQL":
    if config['debug']:
        print "Connect to mysql db: %s, host: %s, user %s" % (config['SQLDB'], config['SQLHost'], config['SQLUser'])

    SQLConnect = MySQLdb.connect(host=config['SQLHost'], user=config['SQLUser'], passwd=config['SQLPassword'],
        db=config['SQLDB'], charset='utf8')
    SQLCursor = SQLConnect.cursor()
else:
    SQLCursor = None
    print "No select valid DB engine"
    sys.exit(1)

if config['debug']:
    print "Connect to xcp master host: " + config['PoolMasterHost'] + ", user: " + config['PoolLogin']

xcpSession = XenAPI.Session(config['PoolMasterHost'])
xcpSession.login_with_password(config['PoolLogin'], config['PoolPassword'])

xapi = xcpSession.xenapi

if configLab['action'] == "create":
    createLab(xapi, SQLCursor, configLab, config)
elif configLab['action'] == "delete":
    deleteLab(xapi, SQLCursor, configLab)
elif configLab['action'] == "clean":
    deleteOddRows(xapi, SQLCursor)

SQLConnect.commit()
