########################
### Settings for lab ###
########################

configLab = {
    'action':       "create",         # create, delete, clean
    #'action':       "delete",
    #'action':       "clean",
    'poolName':     "Main0",
    'domainKrb':    "AVALON.RU",
    'trainer' : '', #login for person who will be able to see and rule any VM of this lab (with such group tag)
    'users':        [
        "ARTZAB",
        "TEST"
    ],
    'folders':      {
        'f':   "/LABs/1C"
    },
    'tags':         {
        't':    "group 1c-labs"
    },
    'networks':     {
        'n':    "1c-lab"
    },
    'templates':    {
        'w':    "T-WinSrv08SP2STD_20120504",
        'u':    "T-Ubuntu10.10"
    },
    'vms':  [
        {
            'template':     'u',
            'folder':       'f',
            'suffix':       ".db.1c-lab.avalon.ru",
            'tags':          ['t'],
            'networks':      ['n']
        },
        {
            'template':     'u',
            'folder':       'f',
            'suffix':       ".app.1c-lab.avalon.ru",
            'tags':          ['t'],
            'networks':      ['n']
        },
        {
            'template':     'w',
            'folder':       'f',
            'suffix':       ".win.1c-lab.avalon.ru",
            'tags':          ['t'],
            'networks':      ['n']
        }
    ]
}