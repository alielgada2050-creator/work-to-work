{
    'name': 'التراخيص والتنسيقات والإغلاقات — الأساس',
    'version': '19.0.1.0.0',
    'summary': 'رخص ومتابعة مختبر وإغلاقات محفوظة في أودو',
    'category': 'Services/Project',
    'license': 'LGPL-3',
    'depends': ['project', 'mail'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/licensing_views.xml',
        'report/permit_report.xml',
    ],
    'demo': ['demo/demo.xml'],
    'application': True,
    'installable': True,
}
