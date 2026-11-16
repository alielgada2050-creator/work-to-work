import base64
from odoo.tests import TransactionCase, tagged
from odoo.tests.common import new_test_user
from odoo.exceptions import AccessError, ValidationError


@tagged('post_install', '-at_install')
class TestLicensing(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.operator = new_test_user(cls.env, login='licensing_operator_test', groups='alasas_licensing.group_operator')
        cls.manager = new_test_user(cls.env, login='licensing_manager_test', groups='alasas_licensing.group_manager')
        cls.reader = new_test_user(cls.env, login='licensing_reader_test', groups='alasas_licensing.group_reader')
        cls.permit = cls.env['alasas.license.permit'].with_user(cls.operator).create({'name': 'TEST-PERMIT-1'})

    def test_reader_cannot_create(self):
        with self.assertRaises(AccessError), self.cr.savepoint():
            self.env['alasas.license.permit'].with_user(self.reader).create({'name': 'NOT-ALLOWED'})

    def test_operator_cannot_approve_via_write(self):
        closure = self.env['alasas.license.closure'].with_user(self.operator).create({'name': 'C1', 'permit_id': self.permit.id})
        with self.assertRaises(AccessError), self.cr.savepoint():
            closure.write({'state': 'approved'})

    def test_manager_needs_successful_report(self):
        closure = self.env['alasas.license.closure'].with_user(self.manager).create({'name': 'C2', 'permit_id': self.permit.id})
        with self.assertRaises(ValidationError), self.cr.savepoint():
            closure.action_approve()

    def test_approval_and_reopen(self):
        lab = self.env['alasas.license.lab'].with_user(self.operator).create({
            'name': 'LAB1', 'permit_id': self.permit.id, 'result': 'pass',
            'report_file': base64.b64encode(b'TEST DOCUMENT ONLY'), 'report_filename': 'test.txt',
        })
        closure = self.env['alasas.license.closure'].with_user(self.manager).create({
            'name': 'C3', 'permit_id': self.permit.id, 'lab_report_id': lab.id,
        })
        closure.action_approve()
        self.assertEqual(self.permit.state, 'closed')
        self.assertEqual(closure.approved_by, self.manager)
        with self.assertRaises(ValidationError), self.cr.savepoint():
            lab.write({'result': 'fail'})
        closure.write({'state': 'review'})
        self.assertEqual(self.permit.state, 'closure')
        self.assertFalse(closure.approved_by)
        lab.write({'result': 'fail'})

    def test_date_and_coordinates(self):
        for values in [{'latitude': 91}, {'length_m': -1}, {'date_start': '2026-12-01', 'date_end': '2026-11-01'}]:
            with self.assertRaises(ValidationError), self.cr.savepoint():
                self.permit.write(values)

    def test_company_isolation(self):
        other = self.env['res.company'].create({'name': 'Licensing Test Other Company'})
        rec = self.env['alasas.license.permit'].create({'name': 'OTHER-CO', 'company_id': other.id, 'user_id': False})
        visible = self.env['alasas.license.permit'].with_user(self.operator).search([('id', '=', rec.id)])
        self.assertFalse(visible)
