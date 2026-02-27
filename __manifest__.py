{
    'name': 'SID - Sale Activity (OV)',
    'version': '15.0.1.0.0',
    'category': 'Sales',
    'summary': 'Personalizaciones de sale.activity (campos, vistas y lógicas) trasladadas a módulo.',
    'author': 'SIDSA',
    'license': 'LGPL-3',
    'depends': [
        'sale',
        'stock',
        'purchase',
        'oct_so_line_info',
        'oct_fecha_contrato_ventas',
    ],
    'data': [
        'views/sale_activity_views.xml',
        'views/sale_activity_tag_rule_views.xml',
        'views/sale_line_activity_integration_views.xml',
        'views/sale_line_activity_wizard_views.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
}
