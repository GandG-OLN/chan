# -*- coding:utf-8 -*-
import logging
from odoo import fields, models

_logger = logging.getLogger(__name__)


class CrossoveredBudget(models.Model):
    _inherit = "gg.crossovered.budget"

    purchase_ids = fields.One2many('purchase.order', 'budget_id', 'Purchases')


class CrossoveredBudgetLines(models.Model):
    _inherit = "gg.crossovered.budget.lines"

    committed_amount = fields.Monetary(compute='_compute_committed_amount',
                                       string='Montant engagé',
                                       help="Montant engagé (Bon de commande).")
    committed_percentage = fields.Float(
        compute='_compute_percentage_committed_amount', string='% Engagé',
        help="Comparaison entre le montant engagé et le montant théorique. Cette mesure vous indique si vous êtes en dessous ou au-dessus du budget..")

    def _compute_committed_amount(self):
        for line in self:
            acc_ids = line.budget_post_id.account_ids.ids
            date_to = line.date_to
            date_from = line.date_from

            if acc_ids:
                # Get all purchase that use budget and between start-end budget line date
                purchase_ids = self.env['purchase.order'].search(
                    [('budget_id', '=', line.budget_id.id), ('date_order', '>=', date_from),
                     ('date_order', '<=', date_to), ('state', 'in', ('purchase', 'done'))])

                pol_obj = self.env['purchase.order.line']
                # Domain to take all move_id with budget
                domain = [('product_id.property_account_expense_id.id', 'in',
                           line.budget_post_id.account_ids.ids),
                          ('order_id', 'in', purchase_ids.ids),
                          ('date_order', '>=', date_from),
                          ('date_order', '<=', date_to)
                          ]
                _logger.info("======= DOMAIN COMMITTED AMOUNT:%s", domain)
                where_query = pol_obj._where_calc(domain)
                pol_obj._apply_ir_rules(where_query, 'read')
                from_clause, where_clause, where_clause_params = where_query.get_sql()
                select = "SELECT sum(price_total) from " + from_clause + " where " + where_clause

            self.env.cr.execute(select, where_clause_params)
            line.committed_amount = -1 * (self.env.cr.fetchone()[0] or 0.0)

    def _compute_percentage_committed_amount(self):
        for line in self:
            line.committed_percentage = float(
                (line.committed_amount or 0.0) / line.planned_amount) if line.committed_amount != 0.00 else 0.00
