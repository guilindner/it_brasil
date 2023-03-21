# Copyright 2020 ForgeFlow S.L. (https://www.forgeflow.com)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import api, models


class CashFlowReportAbstract(models.AbstractModel):
    _name = "report.cash_flow_report.abstract_report"
    _description = "Abstract Report"

    @api.model
    def _get_move_lines_domain_not_reconciled(
        self, company_id, account_ids, partner_ids, only_posted_moves, date_from
    ):
        domain = [
            ("account_id", "in", account_ids),
            ("company_id", "=", company_id),
            ("reconciled", "=", False),
        ]
        if partner_ids:
            domain += [("partner_id", "in", partner_ids)]
        if only_posted_moves:
            domain += [("move_id.state", "=", "posted")]
        else:
            domain += [("move_id.state", "in", ["posted", "draft"])]
        domain += [("date_due", ">=", date_from)]
            
        return domain

    @api.model
    def _get_move_lines_domain_reconciled(
        self, company_id, account_ids, partner_ids, only_posted_moves, date_from, liquidity_accounts_ids
    ):
        domain = [
            ("company_id", "=", company_id),
        ]
        if account_ids:
            domain += [("account_id", "in", account_ids)]
        if liquidity_accounts_ids:
            domain += [("account_id", "in", liquidity_accounts_ids)]
        if account_ids and liquidity_accounts_ids:
            domain += [("account_id", "in", account_ids + liquidity_accounts_ids)]
        if partner_ids:
            domain += [("partner_id", "in", partner_ids)]
        if only_posted_moves:
            domain += [("move_id.state", "=", "posted")]
        else:
            domain += [("move_id.state", "in", ["posted", "draft"])]
        domain += [("date", ">=", date_from)]
            
        return domain

    @api.model
    def _get_new_move_lines_domain(
        self, new_ml_ids, account_ids, company_id, partner_ids, only_posted_moves
    ):
        domain = [
            ("account_id", "in", account_ids),
            ("company_id", "=", company_id),
            ("id", "in", new_ml_ids),
        ]
        if partner_ids:
            domain += [("partner_id", "in", partner_ids)]
        if only_posted_moves:
            domain += [("move_id.state", "=", "posted")]
        else:
            domain += [("move_id.state", "in", ["posted", "draft"])]
        return domain

    def _recalculate_move_lines(
        self,
        move_lines,
        debit_ids,
        credit_ids,
        debit_amount,
        credit_amount,
        ml_ids,
        account_ids,
        company_id,
        partner_ids,
        only_posted_moves,
    ):
        debit_ids = set(debit_ids)
        credit_ids = set(credit_ids)
        in_credit_but_not_in_debit = credit_ids - debit_ids
        reconciled_ids = list(debit_ids) + list(in_credit_but_not_in_debit)
        reconciled_ids = set(reconciled_ids)
        ml_ids = set(ml_ids)
        new_ml_ids = reconciled_ids - ml_ids
        new_ml_ids = list(new_ml_ids)
        new_domain = self._get_new_move_lines_domain(
            new_ml_ids, account_ids, company_id, partner_ids, only_posted_moves
        )
        ml_fields = [
            "id",
            "name",
            "date",
            "move_id",
            "journal_id",
            "account_id",
            "partner_id",
            "amount_residual",
            "date_due",
            "ref",
            "debit",
            "credit",
            "reconciled",
            "currency_id",
            "amount_currency",
            "amount_residual_currency",
            "balance",
        ]
        new_move_lines = self.env["account.move.line"].search_read(
            domain=new_domain, fields=ml_fields
        )
        move_lines = move_lines + new_move_lines
        for move_line in move_lines:
            ml_id = move_line["id"]
            if ml_id in debit_ids:
                move_line["amount_residual"] += debit_amount[ml_id]
            if ml_id in credit_ids:
                move_line["amount_residual"] -= credit_amount[ml_id]
        return move_lines

    def _get_accounts_data(self, accounts_ids):
        accounts = self.env["account.account"].browse(accounts_ids)
        accounts_data = {}
        for account in accounts:
            accounts_data.update(
                {
                    account.id: {
                        "id": account.id,
                        "code": account.code,
                        "name": account.name,
                        "hide_account": False,
                        "group_id": account.group_id.id,
                        "currency_id": account.currency_id or False,
                        "currency_name": account.currency_id.name,
                        "centralized": False,
                    }
                }
            )
        return accounts_data

    def _get_journals_data(self, journals_ids):
        journals = self.env["account.journal"].browse(journals_ids)
        journals_data = {}
        for journal in journals:
            journals_data.update({journal.id: {"id": journal.id, "code": journal.code}})
        return journals_data
