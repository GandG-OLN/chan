# -*- coding: utf-8 -*-
import logging
from odoo import fields, models, api
from odoo.exceptions import UserError
from odoo.osv import expression

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = "account.move"

    def _get_available_budget_by_user(self):
        invoice_date = fields.Date.to_date(self.invoice_date) or fields.Date.today()
        user_id = self.user_id or self.env.user
        return expression.AND(
            [[('state', '=', 'validate')], [('date_from', '<=', invoice_date)], [('date_to', '>=', invoice_date)],
             [('user_allowed_ids', 'in', [user_id.id])], ])

    def _check_exceeded_budget(self):
        if self.approval_request_ids:
            approval_request = len(self.approval_request_ids.filtered(lambda a: a.request_status == "approved"))

            has_exceeded_budget = False if approval_request else self.has_exceeded_budget
        else:
            has_exceeded_budget = self.has_exceeded_budget
        _logger.info("===== HAS EXCEEDED: %s", has_exceeded_budget)
        return has_exceeded_budget

    @api.depends('approval_request_ids')
    def _compute_approvals(self):
        for move in self:
            """
                Update exceeded statut
            """
            move.approval_request_count = len(move.approval_request_ids)
            has_exceeded_budget = move._check_exceeded_budget()
            approval_request_state = 'approved' if move.approval_request_count and len(
                move.approval_request_ids.filtered(lambda a: a.request_status == "approved")) == len(
                move.approval_request_ids) else 'unapproved'

            move.update({
                'has_exceeded_budget': has_exceeded_budget,
                'approval_request_state': approval_request_state
            })

    budget_id = fields.Many2one('gg.crossovered.budget', string='Budget', store=True,
                                domain=lambda self: self._get_available_budget_by_user())
    has_exceeded_budget = fields.Boolean(default=False, store=True)
    approval_request_ids = fields.One2many('approval.request', 'move_id', string="Demande d'approbation",
                                           tracking=True)
    approval_request_count = fields.Integer(compute="_compute_approvals", string='Approbations', copy=False, default=0)
    approval_request_state = fields.Char(string="Statut approbation", readonly=True)

    @api.onchange('budget_id', 'invoice_date', 'invoice_line_ids')
    def _onchange_product_budget(self):
        """
        Check if invoice lines products have available account
        """
        product_ids = self.invoice_line_ids.mapped('product_id')
        if product_ids and self.budget_id and not self.invoice_date:
            raise UserError("Veuillez definir la date de facturation")

        if product_ids and self.budget_id:
            msgs = ""
            # Get all account id
            account_ids = [aml.account_id for aml in
                           self.invoice_line_ids.filtered(lambda aml: aml.product_id in product_ids)]
            for account in account_ids:
                budget_line = self.env['gg.crossovered.budget.lines'].search(expression.AND(
                    [[('budget_id', '=', self.budget_id.id)],
                     [('budget_post_id.account_ids', 'in', account.id)], ]), limit=1)
                if not budget_line:
                    msgs += "Aucun poste budgétaire associé à ce compte %s\n" % account.name
            if msgs:
                raise UserError(msgs)
            else:
                # Verify that the amount does not exceed committed amount
                for account in account_ids:
                    account_amount = sum(
                        self.invoice_line_ids.filtered(lambda aml: aml.account_id.id == account.id).mapped(
                            'price_total'))
                    budget_line = self.env['gg.crossovered.budget.lines'].search(expression.AND(
                        [[('budget_id', '=', self.budget_id.id)],
                         [('budget_post_id.account_ids', 'in', account.id)], ]), limit=1)

                    if abs(budget_line.planned_amount) < abs(budget_line.practical_amount) + account_amount:
                        self.update({'has_exceeded_budget': True})
                    else:
                        self.update({'has_exceeded_budget': False})

    def action_view_approval(self):
        """This function returns an action that display existing approval of
        given purchase order id. When only one found, show the approval request
        immediately.
        """
        result = self.env['ir.actions.act_window']._for_xml_id('approvals.approval_request_action')
        # choose the view_mode accordingly
        if len(self.approval_request_ids) > 1:
            result['domain'] = [('id', 'in', self.approval_request_ids.ids)]
        elif len(self.approval_request_ids) == 1:
            res = self.env.ref('approvals.approval_request_view_form', False)
            form_view = [(res and res.id or False, 'form')]
            if 'views' in result:
                result['views'] = form_view + [(state, view) for state, view in result['views'] if view != 'form']
            else:
                result['views'] = form_view
            result['res_id'] = self.approval_request_ids.id
        else:
            result = {'type': 'ir.actions.act_window_close'}

        return result

    def button_request_for_approval_budget(self):
        for move in self:
            if not move.approval_request_ids:
                approval_category_id = self.env.ref(
                    'gg_account_budget.approval_category_data_account_move_approval_budget')
                approval = self.env['approval.request']

                # Create new approval overrun budget
                result = approval.create(
                    {'name': approval_category_id.sequence_id.next_by_id(), 'request_owner_id': self.env.uid,
                     'category_id': approval_category_id.id,
                     'approval_minimum': approval_category_id.approval_minimum, 'reference': move.name,
                     'move_id': move.id, 'partner_id': move.partner_id.id,
                     'reason': "Demande de dépassement budgétaire pour la facture %s" % move.name, })

                # add approvers for this SO
                if result:
                    for approver in move.budget_id.approver_ids:
                        self.env['approval.approver'].create(
                            {'user_id': approver.user_id.id, 'request_id': result.id, 'status': 'new'})
                    return {'type': 'ir.actions.act_window', 'res_model': 'approval.request', 'view_mode': 'form',
                            'res_id': result.id, 'views': [(False, 'form')], }
                return result
            else:
                raise UserError(
                    "Il existe déja une demande d'approbation pour cette facture avec la référence : %s" %
                    move.approval_request_ids[
                        0].name)

    def action_post(self):
        if self.has_exceeded_budget:
            raise UserError("Cette facture ne peut être confirmée en raison d'un dépassement budgétaire")
        self._post(soft=False)
        return False
