# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Budget Management On Purchase',
    'author': 'G&G Professional services',
    'category': 'Accounting',
    'version': '1.0',
    'description': """Check budget on purchase move""",
    'summary': 'Odoo 14 Budget Management With Purchase',
    'sequence': 10,
    'website': 'https://www.gandgcorp.com',
    'depends': ['purchase', 'approvals', 'gg_account_budget'],
    'license': 'LGPL-3',
    'data': [
        'views/purchase_view.xml',
        'views/account_budget_view.xml',
        'data/approval_category_data.xml',
    ],
}
