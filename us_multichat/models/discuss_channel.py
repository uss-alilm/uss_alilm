import base64
import random

from odoo import api, fields, models, Command
from odoo.exceptions import UserError

ODOO_CHANNEL_TYPES = ["chat", "channel", "livechat", "group"]
MESSENGER_TYPES = ["telegram", "viber", "whatsapp_twilio", "instagram"]


class DiscussChannel(models.Model):
    _inherit = "discuss.channel"

    messenger_operator_id = fields.Many2one("res.partner", string="Operator")

    is_pinned = fields.Boolean(
        "Visible for me",
        compute="_compute_is_pinned",
        inverse="_inverse_is_pinned",
        help="Refresh page after updating",
    )

    @api.model
    def _prepare_multi_livechat_channel_vals(
            self, channel_type, channel_name, partner_ids, bot_id
    ):
        operator = self._get_messenger_operator(bot_id)
        bot = self.env["us.messenger.project"].sudo().browse(bot_id)
        if not bot:
            return False
        operators_ids = set(map(lambda o: o.partner_id.id, bot.operator_ids))
        members = set(partner_ids) - operators_ids
        if operator:
            members = set((operator.partner_id.id,)).union(members)
        return {
            "channel_partner_ids":  [(4, pid) for pid in members],
            "group_public_id": None,
            'messenger_operator_id': operator.partner_id.id if operator else None,
            "channel_type": channel_type,
            "name": channel_name,
        }

    def _get_less_active_operator(self, operator_statuses, operators):
        """ Retrieve the most available operator based on the following criteria:
        - Lowest number of active chats.
        - Not in  a call.
        - If an operator is in a call and has two or more active chats, don't
          give priority over an operator with more conversations who is not in a
          call.

        :param operator_statuses: list of dictionaries containing the operator's
            id, the number of active chats and a boolean indicating if the
            operator is in a call. The list is ordered by the number of active
            chats (ascending) and whether the operator is in a call
            (descending).
        :param operators: recordset of :class:`ResUsers` operators to choose from.
        :return: the :class:`ResUsers` record for the chosen operator
        """
        if not operators:
            return False

        # 1) only consider operators in the list to choose from
        operator_statuses = [
            s for s in operator_statuses if s['messenger_operator_id'] in set(operators.partner_id.ids)
        ]

        # 2) try to select an inactive op, i.e. one w/ no active status (no recent chat)
        active_op_partner_ids = {s['messenger_operator_id'] for s in operator_statuses}
        candidates = operators.filtered(lambda o: o.partner_id.id not in active_op_partner_ids)
        if candidates:
            return random.choice(candidates)

        # 3) otherwise select least active ops, based on status ordering (count + in_call)
        best_status = operator_statuses[0]
        best_status_op_partner_ids = {
            s['messenger_operator_id']
            for s in operator_statuses
            if (s['count'], s['in_call']) == (best_status['count'], best_status['in_call'])
        }
        candidates = operators.filtered(lambda o: o.partner_id.id in best_status_op_partner_ids)
        return random.choice(candidates)

    def _get_messenger_operator(self, bot_id, previous_operator_id=None, lang=None):
        """ Return an operator for a livechat. Try to return the previous
        operator if available. If not, one of the most available operators be
        returned.

        A livechat is considered 'active' if it has at least one message within
        the 30 minutes. This method will try to match the given lang and
        country_id.

        (Some annoying conversions have to be made on the fly because this model
        holds 'res.users' as available operators and the discuss_channel model
        stores the partner_id of the randomly selected operator)

        :param previous_operator_id: id of the previous operator with whom the
            visitor was chatting.
        :param lang: code of the preferred lang of the visitor.
        :param country_id: id of the country of the visitor.
        :return : user
        :rtype : res.users
        """
        bot = self.env["us.messenger.project"].sudo().browse(bot_id)
        if not bot:
            return False
        available_operator_ids = bot.operator_ids.filtered(lambda user: user.im_status in ['online', 'away'])
        if not available_operator_ids:
            return False
        self.env.cr.execute("""
            WITH operator_rtc_session AS (
                SELECT COUNT(DISTINCT s.id) as nbr, member.partner_id as partner_id
                  FROM discuss_channel_rtc_session s
                  JOIN discuss_channel_member member ON (member.id = s.channel_member_id)
                  GROUP BY member.partner_id
            )
            SELECT COUNT(DISTINCT c.id), COALESCE(rtc.nbr, 0) > 0 as in_call, c.messenger_operator_id
            FROM discuss_channel c
            LEFT OUTER JOIN mail_message m ON c.id = m.res_id AND m.model = 'discuss.channel'
            LEFT OUTER JOIN operator_rtc_session rtc ON rtc.partner_id = c.messenger_operator_id
            WHERE c.channel_type IN %s AND c.create_date > ((now() at time zone 'UTC') - interval '24 hours')
            AND m.create_date > ((now() at time zone 'UTC') - interval '30 minutes')
            AND c.messenger_operator_id in %s
            GROUP BY c.messenger_operator_id, rtc.nbr
            ORDER BY COUNT(DISTINCT c.id) < 2 OR rtc.nbr IS NULL DESC, COUNT(DISTINCT c.id) ASC, rtc.nbr IS NULL DESC""",
                            (tuple(MESSENGER_TYPES), tuple(available_operator_ids.partner_id.ids),)
                            )
        operator_statuses = self.env.cr.dictfetchall()
        operator = None
        if not operator:
            operator = self._get_less_active_operator(operator_statuses, available_operator_ids)
        return operator

    def _compute_is_pinned(self):
        # TODO: make batch search via read_group
        for r in self:
            r.is_pinned = self.env["discuss.channel.member"].search_count(
                [
                    ("partner_id", "=", self.env.user.partner_id.id),
                    ("channel_id", "=", r.id),
                    ("is_pinned", "=", True),
                ]
            )

    def _inverse_is_pinned(self):
        # TODO: make batch search via read_group
        for r in self:
            channel_partner = self.env["discuss.channel.member"].search(
                [
                    ("partner_id", "=", self.env.user.partner_id.id),
                    ("channel_id", "=", r.id),
                ]
            )
            # TODO: can channel_partner be empty or more than 1 record?
            channel_partner.is_pinned = r.is_pinned

    def _compute_is_chat(self):
        super(DiscussChannel, self)._compute_is_chat()
        for record in self:
            if record.channel_type not in ODOO_CHANNEL_TYPES:
                record.is_chat = True

    @api.model
    def multi_livechat_info(self):
        field = self.env["discuss.channel"]._fields["channel_type"]
        return {
            "channel_types": {
                key: value
                for key, value in field.selection
                if key not in ODOO_CHANNEL_TYPES
            }
        }

    @api.ondelete(at_uninstall=False)
    def _unlink_forbid(self):
        for record in self:
            if record.channel_type in MESSENGER_TYPES:
                raise UserError('Channel cannot be deleted, only archived')

    def action_archive(self):
        link = self.env['us.messenger.link'].sudo().search(
            [('model', '=', 'discuss.channel'), ('ref2', 'in', self.ids), ('active', '=', True)])
        link.action_archive()
        return super(DiscussChannel, self).action_archive()

    def action_unarchive(self):
        link = self.env['us.messenger.link'].sudo().search(
            [('model', '=', 'discuss.channel'), ('ref2', 'in', self.ids), ('active', '=', False)])
        link.action_unarchive()
        return super(DiscussChannel, self).action_unarchive()
