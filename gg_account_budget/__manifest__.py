# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Budget Management',
    'author': 'G&G Professional services',
    'category': 'Accounting',
    'version': '1.0',
    'description': """Use budgets to compare actual with expected revenues and costs""",
    'summary': 'Odoo 14 Budget Management',
    'sequence': 10,
    'website': 'https://www.gandgcorp.com',
    'depends': ['account', 'account_accountant', 'approvals'],
    'license': 'LGPL-3',
    'assets': {
            'web.assets_backend': [
                'gg_account_budget/static/src/js/account_budget_reproting.js',
            ],
    },
    'data': [
        'security/account_budget_security.xml',
        'security/ir.model.access.csv',
        'views/assets.xml',
        'data/account_budget_reporting.xml',
        'views/account_analytic_account_views.xml',
        'views/account_budget_views.xml',
        'views/account_move_view.xml',
        'views/account_budget_menu_view.xml',
        'views/res_config_settings_views.xml',
        'data/ir_sequence.xml',
        'data/approval_category_data.xml',
    ],
    'qweb': [
        'static/src/xml/template.xml',
    ],

}
