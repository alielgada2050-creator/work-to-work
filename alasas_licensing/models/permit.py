from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError


class Permit(models.Model):
    _name = 'alasas.license.permit'
    _description = 'رخصة أعمال البنية التحتية'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _check_company_auto = True
    _order = 'date_end asc, id desc'

    name = fields.Char('رقم الرخصة', required=True, tracking=True, index=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda s: s.env.company)
    asas_reference = fields.Char('رقم الأساس', tracking=True, index=True)
    scheme = fields.Char('رقم المخطط')
    office = fields.Char('المكتب')
    district = fields.Char('الحي')
    street = fields.Char('الشارع')
    project_id = fields.Many2one('project.project', string='المشروع', check_company=True)
    task_id = fields.Many2one('project.task', string='أمر العمل / المهمة', check_company=True)
    user_id = fields.Many2one('res.users', string='المسؤول', default=lambda s: s.env.user, check_company=True)
    date_start = fields.Date('بداية الرخصة', tracking=True)
    date_end = fields.Date('نهاية الرخصة', tracking=True, index=True)
    days_left = fields.Integer('الأيام المتبقية', compute='_compute_days_left')
    latitude = fields.Float('خط العرض', digits=(10, 7))
    longitude = fields.Float('خط الطول', digits=(10, 7))
    location_verified = fields.Boolean('تم التحقق من الإحداثيات', tracking=True)
    length_m = fields.Float('الطول بالمتر')
    width_m = fields.Float('العرض بالمتر')
    depth_m = fields.Float('العمق بالمتر')
    notes = fields.Text('الملاحظات')
    consultant_status = fields.Char('حالة الاستشاري', tracking=True)
    center_status = fields.Char('حالة المركز', tracking=True)
    state = fields.Selection([
        ('draft', 'مسودة'), ('coordination', 'تنسيق'), ('execution', 'تنفيذ'),
        ('lab', 'بانتظار المختبر'), ('closure', 'مراجعة الإغلاق'),
        ('closed', 'مغلقة'), ('returned', 'معادة'),
    ], default='draft', required=True, tracking=True, index=True)
    lab_ids = fields.One2many('alasas.license.lab', 'permit_id', string='تقارير المختبر')
    closure_ids = fields.One2many('alasas.license.closure', 'permit_id', string='طلبات الإغلاق')

    _unique_number = models.Constraint('UNIQUE(company_id, name)', 'رقم الرخصة موجود بالفعل في الشركة.')

    @api.depends('date_end')
    def _compute_days_left(self):
        today = fields.Date.context_today(self)
        for rec in self:
            rec.days_left = (rec.date_end - today).days if rec.date_end else 0

    @api.constrains('date_start', 'date_end', 'latitude', 'longitude', 'length_m', 'width_m', 'depth_m', 'task_id', 'project_id')
    def _check_values(self):
        for rec in self:
            if rec.date_start and rec.date_end and rec.date_end < rec.date_start:
                raise ValidationError(_('نهاية الرخصة لا تسبق بدايتها.'))
            if not -90 <= rec.latitude <= 90 or not -180 <= rec.longitude <= 180:
                raise ValidationError(_('الإحداثيات خارج النطاق الجغرافي الصحيح.'))
            if min(rec.length_m, rec.width_m, rec.depth_m) < 0:
                raise ValidationError(_('الأبعاد لا يمكن أن تكون سالبة.'))
            if rec.task_id and rec.project_id and rec.task_id.project_id != rec.project_id:
                raise ValidationError(_('المهمة لا تتبع المشروع المحدد.'))

    def _check_close(self):
        if not self.env.user.has_group('alasas_licensing.group_manager'):
            raise AccessError(_('اعتماد الإغلاق متاح لمدير التراخيص فقط.'))
        for rec in self:
            if not rec.closure_ids.filtered(lambda c: c.state == 'approved'):
                raise ValidationError(_('يلزم طلب إغلاق معتمد قبل إغلاق الرخصة.'))

    @api.model_create_multi
    def create(self, vals_list):
        if any(vals.get('state') == 'closed' for vals in vals_list):
            raise ValidationError(_('أنشئ الرخصة ثم اعتمد طلب الإغلاق.'))
        return super().create(vals_list)

    def write(self, vals):
        if vals.get('state') == 'closed':
            self._check_close()
        if any(rec.state == 'closed' for rec in self) and not self.env.user.has_group('alasas_licensing.group_manager'):
            raise AccessError(_('تعديل الرخصة المغلقة متاح للمدير فقط.'))
        return super().write(vals)


class LabReport(models.Model):
    _name = 'alasas.license.lab'
    _description = 'تقرير مختبر الرخصة'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _check_company_auto = True
    _order = 'test_date desc, id desc'

    name = fields.Char('رقم التقرير', required=True)
    company_id = fields.Many2one('res.company', related='permit_id.company_id', store=True, index=True)
    permit_id = fields.Many2one('alasas.license.permit', string='الرخصة', required=True, ondelete='restrict', check_company=True)
    laboratory_id = fields.Many2one('res.partner', string='المختبر', check_company=True)
    test_date = fields.Date('تاريخ الفحص', default=fields.Date.context_today, required=True)
    result = fields.Selection([('pending', 'بانتظار الفحص'), ('pass', 'ناجح'), ('fail', 'راسب')], required=True, default='pending', tracking=True)
    report_file = fields.Binary('ملف التقرير', attachment=True)
    report_filename = fields.Char('اسم الملف')
    notes = fields.Text('الملاحظات')

    @api.constrains('result', 'report_file')
    def _check_report(self):
        for rec in self:
            if rec.result != 'pending' and not rec.report_file:
                raise ValidationError(_('أرفق تقرير المختبر قبل تسجيل نتيجة الفحص.'))

    def write(self, vals):
        approved = self.env['alasas.license.closure'].search_count([
            ('lab_report_id', 'in', self.ids), ('state', '=', 'approved')
        ])
        if approved and set(vals) & {'result', 'report_file', 'permit_id', 'laboratory_id', 'test_date'}:
            raise ValidationError(_('هذا التقرير مرتبط بإغلاق معتمد؛ أعد فتح طلب الإغلاق قبل تعديله.'))
        return super().write(vals)


class Closure(models.Model):
    _name = 'alasas.license.closure'
    _description = 'طلب إغلاق رخصة'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _check_company_auto = True

    name = fields.Char('مرجع الإغلاق', required=True)
    company_id = fields.Many2one('res.company', related='permit_id.company_id', store=True, index=True)
    permit_id = fields.Many2one('alasas.license.permit', string='الرخصة', required=True, ondelete='restrict', check_company=True)
    lab_report_id = fields.Many2one('alasas.license.lab', string='تقرير الفحص المعتمد', check_company=True, ondelete='restrict')
    state = fields.Selection([('draft', 'مسودة'), ('review', 'للمراجعة'), ('approved', 'معتمد'), ('returned', 'معاد')], required=True, default='draft', tracking=True)
    approved_by = fields.Many2one('res.users', string='اعتمد بواسطة', readonly=True)
    approved_at = fields.Datetime('وقت الاعتماد', readonly=True)
    notes = fields.Text('ملاحظات الإغلاق')

    @api.constrains('permit_id', 'lab_report_id', 'state')
    def _check_approval(self):
        for rec in self:
            if rec.lab_report_id and rec.lab_report_id.permit_id != rec.permit_id:
                raise ValidationError(_('التقرير يجب أن يتبع نفس الرخصة.'))
            if rec.state == 'approved' and (not rec.lab_report_id or rec.lab_report_id.result != 'pass' or not rec.lab_report_id.report_file):
                raise ValidationError(_('الإغلاق يتطلب تقرير مختبر ناجحًا ومرفقًا.'))

    @api.model_create_multi
    def create(self, vals_list):
        if any(vals.get('state') == 'approved' or vals.get('approved_by') or vals.get('approved_at') for vals in vals_list):
            raise ValidationError(_('أنشئ الطلب أولًا، ثم اعتمده.'))
        return super().create(vals_list)

    def write(self, vals):
        vals = dict(vals)
        sensitive = {'state', 'permit_id', 'lab_report_id', 'approved_by', 'approved_at'}
        approving = vals.get('state') == 'approved'
        locked = any(rec.state == 'approved' for rec in self) and bool(set(vals) & sensitive)
        if approving or locked or set(vals) & {'approved_by', 'approved_at'}:
            if not self.env.user.has_group('alasas_licensing.group_manager'):
                raise AccessError(_('اعتماد أو تعديل الإغلاق المعتمد متاح للمدير فقط.'))
        if set(vals) & {'approved_by', 'approved_at'}:
            raise ValidationError(_('حقول الاعتماد تسجل آليًا.'))
        if locked and set(vals) & {'permit_id', 'lab_report_id'}:
            raise ValidationError(_('أعد فتح الطلب قبل تغيير الرخصة أو التقرير.'))
        if approving:
            vals.update(approved_by=self.env.uid, approved_at=fields.Datetime.now())
        elif 'state' in vals:
            vals.update(approved_by=False, approved_at=False)
        old_permits = self.filtered(lambda c: c.state == 'approved').mapped('permit_id')
        result = super().write(vals)
        if approving:
            self.mapped('permit_id').write({'state': 'closed'})
        elif 'state' in vals and old_permits:
            old_permits.filtered(lambda p: p.state == 'closed').write({'state': 'closure'})
        return result

    def action_approve(self):
        self.write({'state': 'approved'})

    @api.ondelete(at_uninstall=False)
    def _unlink_except_approved(self):
        if any(rec.state == 'approved' for rec in self):
            raise ValidationError(_('أعد فتح طلب الإغلاق قبل حذفه.'))
