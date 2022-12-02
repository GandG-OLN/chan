# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import logging

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


# ---------------------------------------------------------
# Budgets
# ---------------------------------------------------------
class AccountBudgetPost(models.Model):
    _name = "gg.account.budget.post"
    _order = "name"
    _description = "Poste budgétaire"

    name = fields.Char('Nom', required=True)
    account_ids = fields.Many2many('account.account', 'account_budget_post_rel', 'budget_post_id', 'account_id',
                                   'Compte',
                                   domain=[('deprecated', '=', False)])
    company_id = fields.Many2one('res.company', 'Société', required=True, default=lambda self: self.env.company)

    def _check_account_ids(self, vals):
        # Raise an error to prevent the account.budget.post to have not specified account_ids.
        # This check is done on create because require=True doesn't work on Many2many fields.
        if 'account_ids' in vals:
            account_ids = self.new({'account_ids': vals['account_ids']}, origin=self).account_ids
        else:
            account_ids = self.account_ids
        if not account_ids:
            raise ValidationError(_('Le poste budgetaire doit avoir au moins un compte.'))

    @api.model
    def create(self, vals):
        self._check_account_ids(vals)
        return super(AccountBudgetPost, self).create(vals)

    def write(self, vals):
        self._check_account_ids(vals)
        return super(AccountBudgetPost, self).write(vals)


class CrossoveredBudget(models.Model):
    _name = "gg.crossovered.budget"
    _description = "Budget"
    _inherit = ['mail.thread']

    ref = fields.Char(string='Référence', copy=False, tracking=True, readonly=True)
    name = fields.Char('Nom du budget', required=True, states={'done': [('readonly', True)]})
    type = fields.Selection([
        ('investment', 'Investissement'), ('operation', 'Exploitation')],
        string="Type")
    user_id = fields.Many2one('res.users', 'Responsable', default=lambda self: self.env.user)
    date_from = fields.Date('Date de debut', required=True, states={'done': [('readonly', True)]})
    date_to = fields.Date('Date de fin', required=True, states={'done': [('readonly', True)]})
    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('cancel', 'Annulé'),
        ('confirm', 'Confirmé'),
        ('validate', 'Validé'),
        ('done', 'Fait')
    ], 'Statut', default='draft', index=True, required=True, readonly=True, copy=False, tracking=True)
    budget_lines = fields.One2many('gg.crossovered.budget.lines', 'budget_id', 'Lignes budgétaires',
                                   states={'done': [('readonly', True)]}, copy=True, )
    company_id = fields.Many2one('res.company', 'Société', required=True, default=lambda self: self.env.company)
    approver_ids = fields.One2many('gg.crossovered.budget.approver', 'budget_id', 'Approbateurs', required=True)
    user_allowed_ids = fields.Many2many('res.users', 'gg_budget_allowed_user_rel', 'budget_id', 'user_id',
                                        string='Utilisateurs autorisés', required=True)

    def action_budget_confirm(self):
        if not self.approver_ids:
            ValidationError('Pour confirmer un budget il faut définir au moins un approbateur')
        self.write({'state': 'confirm'})

    def action_budget_draft(self):
        self.write({'state': 'draft'})

    def action_budget_validate(self):
        reference = self.ref
        if not self.user_allowed_ids:
            ValidationError('Pour confirmer un budget il faut définir au moins un utilisateur du budget')
        # Implement sequence
        if not reference:
            sequence_id = self.env.ref('gg_account_budget.account_budget_sequence')
            reference = sequence_id.next_by_id(sequence_date=self.date_from)

        self.write({'state': 'validate', 'ref': reference})

    def action_budget_cancel(self):
        self.write({'state': 'cancel'})

    def action_budget_done(self):
        self.write({'state': 'done'})


class CrossoveredBudgetLines(models.Model):
    _name = "gg.crossovered.budget.lines"
    _description = "Lignes budgétaires"

    name = fields.Char(compute='_compute_line_name')
    budget_id = fields.Many2one('gg.crossovered.budget', 'Budget', ondelete='cascade', index=True,
                                required=True)
    analytic_account_id = fields.Many2one('account.analytic.account', 'Compte analytique')
    analytic_group_id = fields.Many2one('account.analytic.group', 'Groupe analytique',
                                        related='analytic_account_id.group_id', readonly=True)
    budget_post_id = fields.Many2one('gg.account.budget.post', 'Poste budgétaire')
    date_from = fields.Date('Date de debut', required=True)
    date_to = fields.Date('Date de fin', required=True)
    paid_date = fields.Date('Paid Date')
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id', readonly=True)
    planned_amount = fields.Monetary(
        'Montant planifié', required=True,
        help="Montant que vous prévoyez de gagner/dépenser. Enregistrez un montant positif s'il s'agit d'une recette et un montant négatif s'il s'agit d'un coût.")
    practical_amount = fields.Monetary(
        compute='_compute_practical_amount', string='Montant realisé', help="Montant realisé (Facturation).")
    theoritical_amount = fields.Monetary(
        compute='_compute_theoritical_amount', string='Montant théorique',
        help="Montant que vous êtes censé avoir gagné/dépensé à cette date.")
    practical_percentage = fields.Float(
        compute='_compute_percentage_practical_amount', string='% Réalisé',
        help="Comparaison entre le montant réalisé et le montant théorique. Cette mesure vous indique si vous êtes en dessous ou au-dessus du budget..")
    company_id = fields.Many2one(related='budget_id.company_id', comodel_name='res.company',
                                 string='Société', store=True, readonly=True)
    is_above_budget = fields.Boolean(compute='_is_above_budget')
    budget_state = fields.Selection(related='budget_id.state', string='Statut',
                                    store=True, readonly=True)

    def _is_above_budget(self):
        for line in self:
            if line.theoritical_amount >= 0:
                line.is_above_budget = line.practical_amount > line.theoritical_amount
            else:
                line.is_above_budget = line.practical_amount < line.theoritical_amount

    def _compute_line_name(self):
        # just in case someone opens the budget line in form view
        computed_name = self.budget_id.name
        if self.budget_post_id:
            computed_name += ' - ' + self.budget_post_id.name
        if self.analytic_account_id:
            computed_name += ' - ' + self.analytic_account_id.name
        self.name = computed_name

    def _compute_practical_amount(self):
        for line in self:
            acc_ids = line.budget_post_id.account_ids.ids
            date_to = line.date_to
            date_from = line.date_from
            if line.analytic_account_id.id:
                analytic_line_obj = self.env['account.analytic.line']
                domain = [('account_id', '=', line.analytic_account_id.id),
                          ('date', '>=', date_from),
                          ('date', '<=', date_to),
                          ]
                if acc_ids:
                    domain += [('general_account_id', 'in', acc_ids)]

                where_query = analytic_line_obj._where_calc(domain)
                analytic_line_obj._apply_ir_rules(where_query, 'read')
                from_clause, where_clause, where_clause_params = where_query.get_sql()
                select = "SELECT SUM(amount) from " + from_clause + " where " + where_clause

            else:
                # Extract invoices ids
                move_ids = self.env['account.move'].search(
                    [('budget_id', '=', line.budget_id.id), ('invoice_date', '>=', date_from), ('invoice_date', '<=', date_to),
                     ('state', '=', 'posted')])

                # move_ids = purchase_ids.mapped('invoice_ids.id')

                aml_obj = self.env['account.move.line']
                # Domain to take all move_id with budget
                domain = [('account_id', 'in',
                           line.budget_post_id.account_ids.ids),
                          ('move_id', 'in', move_ids.ids),
                          ('date', '>=', date_from),
                          ('date', '<=', date_to)
                          ]
                _logger.info("====== PRATICAL AMOUNT %s", domain)
                where_query = aml_obj._where_calc(domain)
                aml_obj._apply_ir_rules(where_query, 'read')
                from_clause, where_clause, where_clause_params = where_query.get_sql()
                select = "SELECT sum(credit)-sum(debit) from " + from_clause + " where " + where_clause

            self.env.cr.execute(select, where_clause_params)
            line.practical_amount = self.env.cr.fetchone()[0] or 0.0

    def _compute_theoritical_amount(self):
        # beware: 'today' variable is mocked in the python tests and thus, its implementation matter
        today = fields.Date.today()
        for line in self:
            if line.paid_date:
                if today <= line.paid_date:
                    theo_amt = 0.00
                else:
                    theo_amt = line.planned_amount
            else:
                line_timedelta = line.date_to - line.date_from
                elapsed_timedelta = today - line.date_from

                if elapsed_timedelta.days < 0:
                    # If the budget line has not started yet, theoretical amount should be zero
                    theo_amt = 0.00
                elif line_timedelta.days > 0 and today < line.date_to:
                    # If today is between the budget line date_from and date_to
                    theo_amt = (
                                       elapsed_timedelta.total_seconds() / line_timedelta.total_seconds()) * line.planned_amount
                else:
                    theo_amt = line.planned_amount
            line.theoritical_amount = theo_amt

    def _compute_percentage_practical_amount(self):
        for line in self:
            line.practical_percentage = float(
                (line.practical_amount or 0.0) / line.planned_amount) if line.practical_amount != 0.00 else 0.00

    @api.constrains('budget_post_id', 'analytic_account_id')
    def _must_have_analytical_or_budgetary_or_both(self):
        if not self.analytic_account_id and not self.budget_post_id:
            raise ValidationError(
                _("Vous devez définir au moins un poste budgétaire ou un compte analytique sur une ligne budgétaire.."))

    def action_open_budget_entries(self):
        if self.analytic_account_id:
            # if there is an analytic account, then the analytic items are loaded
            action = self.env['ir.actions.act_window']._for_xml_id('analytic.account_analytic_line_action_entries')
            action['domain'] = [('account_id', '=', self.analytic_account_id.id),
                                ('date', '>=', self.date_from),
                                ('date', '<=', self.date_to)
                                ]
            if self.budget_post_id:
                action['domain'] += [('general_account_id', 'in', self.budget_post_id.account_ids.ids)]
        else:
            # Extract invoices ids
            move_ids = self.env['account.move'].search(
                [('budget_id', '=', self.budget_id.id), ('date', '>=', self.date_from), ('date', '<=', self.date_to)])

            _logger.info("===== MOVE IDS: %s", move_ids)

            # otherwise the journal entries booked on the accounts of the budgetary postition are opened
            action = self.env['ir.actions.act_window']._for_xml_id('account.action_account_moves_all_a')
            action['domain'] = [('account_id', 'in',
                                 self.budget_post_id.account_ids.ids),
                                ('move_id', 'in', move_ids.ids),
                                ('date', '>=', self.date_from),
                                ('date', '<=', self.date_to)
                                ]
            _logger.info("===== DOMAIN MOVE LINE ENTRIES: %s", self.budget_id)
        return action

    @api.constrains('date_from', 'date_to')
    def _line_dates_between_budget_dates(self):
        for rec in self:
            budget_date_from = rec.budget_id.date_from
            budget_date_to = rec.budget_id.date_to
            if rec.date_from:
                date_from = rec.date_from
                if date_from < budget_date_from or date_from > budget_date_to:
                    raise ValidationError(
                        _('La "Date de debut" de la ligne budgétaire doit etre incluse dans la period du budget'))
            if rec.date_to:
                date_to = rec.date_to
                if date_to < budget_date_from or date_to > budget_date_to:
                    raise ValidationError(
                        _('La "Date de fin" de la ligne budgétaire doit etre incluse dans la period du budget<'))


class CrossoveredBudgetApprover(models.Model):
    _name = 'gg.crossovered.budget.approver'
    _description = "Approbateurs"
    _rec_name = "user_id"

    budget_id = fields.Many2one('gg.crossovered.budget', 'Budget')
    user_id = fields.Many2one('res.users', string="Propriétaire", check_company=True,
                              domain="[('share', '=', False)]")
    rate = fields.Integer("Excédant")
