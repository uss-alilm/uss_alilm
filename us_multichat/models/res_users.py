
from odoo import models


class Users(models.Model):
    _inherit = "res.users"

    def _init_messaging(self, store):
        super()._init_messaging(store)
        # Треба буде проверить
        store.add({'us_multichat':self.env["discuss.channel"].multi_livechat_info()})
