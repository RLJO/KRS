import re
import base64
import datetime

from odoo import fields, models, api, _, tools
from odoo.addons.iap import jsonrpc
from odoo.exceptions import UserError
from odoo.tools.safe_eval import safe_eval
import logging
from odoo import SUPERUSER_ID
from dateutil.relativedelta import relativedelta
from odoo.exceptions import RedirectWarning, UserError, ValidationError, AccessError
from odoo.tools import float_is_zero, float_compare, safe_eval, date_utils, email_split, email_escape_char, email_re
from odoo.tools.misc import formatLang, format_date, get_lang

from datetime import date, timedelta
from itertools import groupby
from itertools import zip_longest
from hashlib import sha256
from json import dumps

import json
import re

_logger = logging.getLogger(__name__)


class StockPickingInherit(models.Model):
    _inherit = 'stock.picking'

    pre_advice = fields.Boolean("Pre Advice")
    amount_of_pallets = fields.Float("Amount of pallets")
    # measure_pallets = fields.Char(string="Measurements pallet", placeholder="Brut weight and LxWxH")
    amount_of_case_pallets = fields.Float("Amount of cases per pallet")
    measure_height = fields.Char("Height")
    measure_length = fields.Char("Length")
    pre_advice_type = fields.Selection([('transfer', 'Transfer'), ('return', 'Return')], String="Pre Advice Type",
                                       default="transfer")
    depart_date = fields.Date("Depart Date")
    arrival_date = fields.Date("Arrival Date")

    @api.onchange('partner_id','picking_type_id','location_id')
    def _onchange_get_seller_location(self):
        for record in self:
            if record.pre_advice and record.partner_id and record.picking_type_id:
                if record.picking_type_id.default_location_src_id == record.location_id:
                    record.location_id = record.partner_id.seller_location_id.id


    @api.onchange('pre_advice_type')
    def _onchange_get_location_swipe(self):
        for record in self:
            if record.location_id and record.location_dest_id:
                source = record.location_dest_id
                dest = record.location_id
                record.location_id = source
                record.location_dest_id = dest

class StockLocationInherit(models.Model):
    _inherit = 'stock.location'

    seller_id = fields.Many2one("res.partner", string="Seller")

# class AccountMoveInherit(models.Model):
#     _inherit = 'account.move'
#
#     # @api.depends(
#     #     'line_ids.debit',
#     #     'line_ids.credit',
#     #     'line_ids.currency_id',
#     #     'line_ids.amount_currency',
#     #     'line_ids.amount_residual',
#     #     'line_ids.amount_residual_currency',
#     #     'line_ids.payment_id.state')
#     # def _compute_amount_custom(self):
#     #     invoice_ids = [move.id for move in self if move.id and move.is_invoice(include_receipts=True)]
#     #     self.env['account.payment'].flush(['state'])
#     #     if invoice_ids:
#     #         self._cr.execute(
#     #             '''
#     #                 SELECT move.id
#     #                 FROM account_move move
#     #                 JOIN account_move_line line ON line.move_id = move.id
#     #                 JOIN account_partial_reconcile part ON part.debit_move_id = line.id OR part.credit_move_id = line.id
#     #                 JOIN account_move_line rec_line ON
#     #                     (rec_line.id = part.debit_move_id AND line.id = part.credit_move_id)
#     #                 JOIN account_payment payment ON payment.id = rec_line.payment_id
#     #                 JOIN account_journal journal ON journal.id = rec_line.journal_id
#     #                 WHERE payment.state IN ('posted', 'sent')
#     #                 AND journal.post_at = 'bank_rec'
#     #                 AND move.id IN %s
#     #             UNION
#     #                 SELECT move.id
#     #                 FROM account_move move
#     #                 JOIN account_move_line line ON line.move_id = move.id
#     #                 JOIN account_partial_reconcile part ON part.debit_move_id = line.id OR part.credit_move_id = line.id
#     #                 JOIN account_move_line rec_line ON
#     #                     (rec_line.id = part.credit_move_id AND line.id = part.debit_move_id)
#     #                 JOIN account_payment payment ON payment.id = rec_line.payment_id
#     #                 JOIN account_journal journal ON journal.id = rec_line.journal_id
#     #                 WHERE payment.state IN ('posted', 'sent')
#     #                 AND journal.post_at = 'bank_rec'
#     #                 AND move.id IN %s
#     #             ''', [tuple(invoice_ids), tuple(invoice_ids)]
#     #         )
#     #         in_payment_set = set(res[0] for res in self._cr.fetchall())
#     #     else:
#     #         in_payment_set = {}
#     #
#     #     for move in self:
#     #         total_untaxed = 0.0
#     #         total_untaxed_currency = 0.0
#     #         total_tax = 0.0
#     #         total_tax_currency = 0.0
#     #         total_residual = 0.0
#     #         total_residual_currency = 0.0
#     #         total = 0.0
#     #         total_currency = 0.0
#     #         currencies = set()
#     #
#     #         for line in move.line_ids:
#     #             if line.currency_id:
#     #                 currencies.add(line.currency_id)
#     #
#     #             if move.is_invoice(include_receipts=True):
#     #                 # === Invoices ===
#     #
#     #                 if not line.exclude_from_invoice_tab:
#     #                     # Untaxed amount.
#     #                     total_untaxed += line.balance
#     #                     total_untaxed_currency += line.amount_currency
#     #                     total += line.balance
#     #                     total_currency += line.amount_currency
#     #                 elif line.tax_line_id:
#     #                     # Tax amount.
#     #                     total_tax += line.balance
#     #                     total_tax_currency += line.amount_currency
#     #                     total += line.balance
#     #                     total_currency += line.amount_currency
#     #                 elif line.account_id.user_type_id.type in ('receivable', 'payable'):
#     #                     # Residual amount.
#     #                     total_residual += line.amount_residual
#     #                     total_residual_currency += line.amount_residual_currency
#     #             else:
#     #                 # === Miscellaneous journal entry ===
#     #                 if line.debit:
#     #                     total += line.balance
#     #                     total_currency += line.amount_currency
#     #
#     #         if move.type == 'entry' or move.is_outbound():
#     #             sign = 1
#     #         else:
#     #             sign = -1
#     #         move.amount_untaxed = sign * (total_untaxed_currency if len(currencies) == 1 else total_untaxed)
#     #         move.amount_tax = sign * (total_tax_currency if len(currencies) == 1 else total_tax)
#     #         move.amount_total = sign * (total_currency if len(currencies) == 1 else total)
#     #         move.amount_residual = -sign * (total_residual_currency if len(currencies) == 1 else total_residual)
#     #         move.amount_untaxed_signed = -total_untaxed
#     #         move.amount_tax_signed = -total_tax
#     #         move.amount_total_signed = abs(total) if move.type == 'entry' else -total
#     #         move.amount_residual_signed = total_residual
#     #
#     #         currency = len(currencies) == 1 and currencies.pop() or move.company_id.currency_id
#     #         is_paid = currency and currency.is_zero(move.amount_residual) or not move.amount_residual
#     #
#     #         # Compute 'invoice_payment_state'.
#     #         if move.type == 'entry':
#     #             move.invoice_payment_state = False
#     #         elif move.state == 'posted' and is_paid:
#     #             if move.id in in_payment_set:
#     #                 move.invoice_payment_state = 'in_payment'
#     #             else:
#     #                 move.invoice_payment_state = 'paid'
#     #         else:
#     #             move.invoice_payment_state = 'not_paid'
#
#     @api.depends('line_ids.price_subtotal', 'line_ids.tax_base_amount', 'line_ids.tax_line_id', 'partner_id',
#                  'currency_id', 'pre_advice_charge')
#     def _compute_invoice_taxes_by_group(self):
#         ''' Helper to get the taxes grouped according their account.tax.group.
#         This method is only used when printing the invoice.
#         '''
#         for move in self:
#             pf = 0.0
#             lang_env = move.with_context(lang=move.partner_id.lang).env
#             tax_lines = move.line_ids.filtered(lambda line: line.tax_line_id)
#             if tax_lines and not pf and move.pre_advice_charge:
#                 tax_lines['tax_base_amount'] += move.pre_advice_charge
#             tax_balance_multiplicator = -1 if move.is_inbound(True) else 1
#             res = {}
#             # There are as many tax line as there are repartition lines
#             done_taxes = set()
#             for line in tax_lines:
#                 res.setdefault(line.tax_line_id.tax_group_id, {'base': 0.0, 'amount': 0.0})
#                 res[line.tax_line_id.tax_group_id]['amount'] += tax_balance_multiplicator * (
#                     line.amount_currency if line.currency_id else line.balance)
#                 tax_key_add_base = tuple(move._get_tax_key_for_group_add_base(line))
#                 if tax_key_add_base not in done_taxes:
#                     if line.currency_id and line.company_currency_id and line.currency_id != line.company_currency_id:
#                         amount = line.company_currency_id._convert(line.tax_base_amount, line.currency_id,
#                                                                    line.company_id, line.date or fields.Date.today())
#                     else:
#                         amount = line.tax_base_amount
#                     res[line.tax_line_id.tax_group_id]['base'] += amount
#                     # The base should be added ONCE
#                     done_taxes.add(tax_key_add_base)
#
#             # At this point we only want to keep the taxes with a zero amount since they do not
#             # generate a tax line.
#             for line in move.line_ids:
#                 for tax in line.tax_ids.flatten_taxes_hierarchy():
#                     if tax.tax_group_id not in res:
#                         res.setdefault(tax.tax_group_id, {'base': 0.0, 'amount': 0.0})
#                         res[tax.tax_group_id]['base'] += tax_balance_multiplicator * (
#                             line.amount_currency if line.currency_id else line.balance)
#
#             res = sorted(res.items(), key=lambda l: l[0].sequence)
#             for x in res:
#                x[1]['base']+=20
#                x[1]['amount']+=1.4
#             move.amount_by_group = [(
#                 group.name, amounts['amount'],
#                 amounts['base'],
#                 formatLang(lang_env, amounts['amount'], currency_obj=move.currency_id),
#                 formatLang(lang_env, amounts['base'], currency_obj=move.currency_id),
#                 len(res),
#                 group.id
#             ) for group, amounts in res]
#
#     @api.depends('invoice_line_ids.price_subtotal')
#     def _compute_line_total_amount(self):
#         for record in self:
#             amount=0.0
#             if record.invoice_line_ids:
#                 for line in record.invoice_line_ids:
#                     amount+=line.price_subtotal
#             record.line_total_amount = amount
#
#
#     pre_advice_charge = fields.Monetary(string='Pre Advice', store=True, tracking=True,currency_field='company_currency_id')
#     line_total_amount = fields.Monetary(string='Total', store=True, readonly=True, tracking=True,
#         compute='_compute_line_total_amount')
#     amount_by_group = fields.Binary(string="Tax amount by group",
#                                     compute='_compute_invoice_taxes_by_group')
#
#     @api.onchange('pre_advice_charge','amount_untaxed')
#     def _onchange_pre_advice_charge(self):
#         if self.pre_advice_charge:
#             self.amount_untaxed = self.amount_untaxed + self.pre_advice_charge
#         else:
#             self.amount_untaxed = self.line_total_amount
