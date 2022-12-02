# -*- coding: utf-8 -*-

import logging
from datetime import datetime
from dateutil.relativedelta import relativedelta
from odoo import models, api, fields
from odoo.http import request

_logger = logging.getLogger(__name__)

LABELS = ['planned', 'practical', 'committed']


class DashboardBudget(models.Model):
    _inherit = 'gg.crossovered.budget'

    @api.model
    def get_currency(self):
        company_ids = self.get_current_company_value()
        if 0 in company_ids:
            company_ids.remove(0)
        current_company_id = company_ids[0]
        current_company = self.env['res.company'].browse(current_company_id)
        default = current_company.currency_id or self.env.ref('base.main_company').currency_id
        lang = self.env.user.lang
        if not lang:
            lang = 'fr_FR'
        lang = lang.replace("_", '-')
        currency = {'position': default.position, 'symbol': default.symbol, 'language': lang}
        return currency

    def _cr_execute(self, query, params=None):
        ''' Similar to self._cr.execute but allowing some custom behavior like shadowing the account_move_line table
        to another one like account_reports_cash_basis does.
        :param query:   The query to be executed by the report.
        :param params:  The optional params of the _cr.execute method.
        '''
        return self._cr.execute(query, params)

    def get_current_company_value(self):
        cookies_cids = [int(r) for r in request.httprequest.cookies.get('cids').split(",")] \
            if request.httprequest.cookies.get('cids') \
            else [request.env.user.company_id.id]

        for company_id in cookies_cids:
            if company_id not in self.env.user.company_ids.ids:
                cookies_cids.remove(company_id)
        if not cookies_cids:
            cookies_cids = [self.env.company.id]
        if len(cookies_cids) == 1:
            cookies_cids.append(0)
        return cookies_cids

    @api.model
    def get_budget_reporting_this_year(self, param):
        _logger.info('======= DATE: %s', param)
        filter_date = fields.Date().today() if not param else datetime.strptime(param, '%Y-%m-%d')
        date_year = '%{}'.format(str(filter_date.year))
        date_month = '%{}-{}'.format(str(filter_date.month), str(filter_date.year))
        # Process with ORM
        record_year = self.env['gg.crossovered.budget'].search(
            [('state', 'in', ('validate', 'done')), ('date_from', 'like', date_year), ('date_to', 'like', date_year)])
        record_month = self.env['gg.crossovered.budget'].search(
            [('state', 'in', ('validate', 'done')), ('date_from', 'like', date_month),
             ('date_to', 'ilike', date_month)])

        return {
            'total_planned_year': abs(sum(record_year.budget_lines.mapped('planned_amount'))),
            'total_practical_year': abs(sum(record_year.budget_lines.mapped('practical_amount'))),
            'total_committed_year': abs(sum(record_year.budget_lines.mapped('committed_amount'))),
            # Monthly
            'total_planned_month': abs(sum(record_month.budget_lines.mapped('planned_amount'))),
            'total_practical_month': abs(sum(record_month.budget_lines.mapped('practical_amount'))),
            'total_committed_month': abs(sum(record_month.budget_lines.mapped('committed_amount'))),
        }

    @api.model
    def get_budget_post_reporting_table(self, param):
        filter_date = fields.Date().today() if not param else datetime.strptime(param, '%Y-%m-%d')
        records = []
        date_year = '%{}'.format(str(filter_date.year))
        budget_post_ids = self.env['gg.account.budget.post'].search([])
        for post in budget_post_ids:
            lines = self.env['gg.crossovered.budget.lines'].search(
                [('budget_post_id', '=', post.id), ('budget_state', 'in', ('validate', 'done')),
                 ('date_from', 'like', date_year), ('date_to', 'like', date_year)])
            records.append({
                'name': post.name,
                'total_planned_year': abs(sum(lines.mapped('planned_amount'))),
                'total_practical_year': abs(sum(lines.mapped('practical_amount'))),
                'total_committed_year': abs(sum(lines.mapped('committed_amount'))),
                'total_available_year': abs(sum(lines.mapped('planned_amount'))) - abs(sum(lines.mapped('practical_amount'))),
            })
        _logger.info('========== POSTS REPORTING: %s', records)
        return records

    @api.model
    def get_budget_by_last_five_year(self, param):
        labels = []
        datasets = {
            'total_planned_year': [],
            'total_practical_year': [],
            'total_committed_year': [],
        }
        filter_date = fields.Date().today() if not param else datetime.strptime(param, '%Y-%m-%d')
        date_previous, date_end = filter_date - relativedelta(years=5), filter_date
        while date_previous <= date_end:
            date_year = '%{}'.format(date_previous.year)
            record_year = self.env['gg.crossovered.budget'].search(
                [('state', 'in', ('validate', 'done')), ('date_from', 'like', date_year),
                 ('date_to', 'like', date_year)])
            _logger.info('====== YEAR: %s, LINES: %s', date_year, record_year)
            labels.append(date_previous.year)
            for label in LABELS:
                datasets['total_%s_year' % label].append(abs(sum(record_year.budget_lines.mapped('%s_amount' % label))))

            date_previous = date_previous + relativedelta(years=1)
        return {'labels': labels, 'datasets': datasets}
