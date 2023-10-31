# Copyright 2017 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from dateutil.relativedelta import relativedelta

from odoo import _, fields

from .common import TestMaintenancePlanBase


class TestMaintenancePlan(TestMaintenancePlanBase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.today_date = fields.Date.from_string("2023-01-25")

    def test_name_get(self):
        self.assertEqual(
            self.maintenance_plan_1.name_get()[0][1],
            _(
                "Unnamed %(void)s plan (%(eqpmnt)s)",
                void="",
                eqpmnt=self.maintenance_plan_1.equipment_id.name,
            ),
        )
        self.assertEqual(
            self.maintenance_plan_2.name_get()[0][1],
            _(
                "Unnamed %(kind)s plan (%(eqpmnt)s)",
                kind=self.maintenance_plan_2.maintenance_kind_id.name,
                eqpmnt=self.maintenance_plan_2.equipment_id.name,
            ),
        )
        self.assertEqual(
            self.maintenance_plan_3.name_get()[0][1], self.maintenance_plan_3.name
        )

    def test_next_maintenance_date_01(self):
        # We set start maintenance date tomorrow and check next maintenance
        # date has been correctly computed
        self.maintenance_plan_1.start_maintenance_date = "2023-01-24"
        # Check next maintenance date is 1 month from start date
        self.assertEqual(
            self.maintenance_plan_1.next_maintenance_date,
            fields.Date.from_string("2023-02-24"),
        )

    def test_next_maintenance_date_02(self):
        self.cron.method_direct_trigger()
        # Check maintenance plan dates
        self.assertEqual(
            self.maintenance_plan_1.start_maintenance_date, self.today_date
        )
        self.assertEqual(self.maintenance_plan_1.next_maintenance_date, self.today_date)
        # Check information from generated_requests
        generated_requests = self.maintenance_request_obj.search(
            [("maintenance_plan_id", "=", self.maintenance_plan_1.id)],
            order="schedule_date asc",
        )
        self.assertEqual(len(generated_requests), 3)
        maintenance_1 = generated_requests[0]
        # First maintenance was planned 2023-01-25
        self.assertEqual(maintenance_1.request_date, self.today_date)
        # Complete request:
        maintenance_1.stage_id = self.done_stage
        # Check next one:
        maintenance_2 = generated_requests[1]
        # This should be expected 2023-02-25
        self.assertEqual(
            maintenance_2.request_date, fields.Date.from_string("2023-02-25")
        )
        # Complete request and Check next one:
        maintenance_2.stage_id = self.done_stage
        maintenance_3 = generated_requests[2]
        # This one should be expected 2023-03-25
        self.assertEqual(
            maintenance_3.request_date, fields.Date.from_string("2023-03-25")
        )
        # Move it to a date before `start_maintenance_date` (the request should
        # be ignored)
        past_date = fields.Date.from_string("2022-12-25")
        maintenance_3.request_date = past_date
        self.assertNotEqual(self.maintenance_plan_1.next_maintenance_date, past_date)
        self.assertEqual(
            self.maintenance_plan_1.next_maintenance_date,
            fields.Date.from_string("2023-03-25"),
        )
        # Move the request_date far into the future:
        future_date = fields.Date.from_string("2023-05-25")
        maintenance_3.request_date = future_date
        self.assertEqual(self.maintenance_plan_1.next_maintenance_date, future_date)
        # Complete request in that date, next expected date should be 1 month
        # after latest request done.:
        maintenance_3.stage_id = self.done_stage
        self.assertEqual(
            self.maintenance_plan_1.next_maintenance_date,
            fields.Date.from_string("2023-06-25"),
        )

    def test_generate_requests(self):
        self.cron.method_direct_trigger()
        generated_requests = self.maintenance_request_obj.search(
            [("maintenance_plan_id", "=", self.maintenance_plan_1.id)],
            order="schedule_date asc",
        )
        self.assertEqual(len(generated_requests), 3)
        self.assertEqual(
            fields.Date.to_date(generated_requests[0].schedule_date), self.today_date
        )
        self.assertEqual(
            fields.Date.to_date(generated_requests[1].schedule_date),
            fields.Date.from_string("2023-02-25"),
        )
        self.assertEqual(
            fields.Date.to_date(generated_requests[2].schedule_date),
            fields.Date.from_string("2023-03-25"),
        )
        generated_request = self.maintenance_request_obj.search(
            [("maintenance_plan_id", "=", self.maintenance_plan_4.id)], limit=1
        )
        self.assertEqual(
            generated_request.name,
            _(
                "Preventive Maintenance (%(kind)s) - %(plan)s",
                kind=self.weekly_kind.name,
                plan=self.maintenance_plan_4.name,
            ),
        )

    def test_generate_requests2(self):
        self.cron.method_direct_trigger()
        generated_requests = self.maintenance_request_obj.search(
            [("maintenance_plan_id", "=", self.maintenance_plan_1.id)],
            order="schedule_date asc",
        )

        self.assertEqual(len(generated_requests), 3)
        # We set plan start_maintenanca_date to a future one. New requests should take
        # into account this new date.
        new_date = fields.Date.from_string("2023-04-25")
        self.maintenance_plan_1.next_maintenance_date = new_date
        self.maintenance_plan_1.maintenance_plan_horizon = 3
        self.cron.method_direct_trigger()
        generated_requests = self.maintenance_request_obj.search(
            [("maintenance_plan_id", "=", self.maintenance_plan_1.id)],
            order="schedule_date asc",
        )
        self.assertEqual(len(generated_requests), 4)
        self.assertEqual(generated_requests[-1].request_date, new_date)

    def test_get_relativedelta(self):
        plan = self.maintenance_plan_1
        result = plan.get_relativedelta(1, "day")
        self.assertEqual(relativedelta(days=1), result)
        result = plan.get_relativedelta(1, "week")
        self.assertEqual(relativedelta(weeks=1), result)
        result = plan.get_relativedelta(1, "month")
        self.assertEqual(relativedelta(months=1), result)
        result = plan.get_relativedelta(1, "year")
        self.assertEqual(relativedelta(years=1), result)

    def test_generate_requests_inactive_equipment(self):
        self.equipment_1.active = False
        self.cron.method_direct_trigger()
        generated_requests = self.maintenance_request_obj.search(
            [("maintenance_plan_id", "=", self.maintenance_plan_1.id)],
            order="schedule_date asc",
        )
        self.assertEqual(len(generated_requests), 0)
        self.equipment_1.active = True
        self.cron.method_direct_trigger()
        generated_requests = self.maintenance_request_obj.search(
            [("maintenance_plan_id", "=", self.maintenance_plan_1.id)],
            order="schedule_date asc",
        )
        self.assertEqual(len(generated_requests), 3)

    def test_maintenance_request_report(self):
        self.cron.method_direct_trigger()
        generated_request = self.maintenance_request_obj.search(
            [("maintenance_plan_id", "=", self.maintenance_plan_1.id)],
            order="schedule_date asc",
            limit=1,
        )
        generated_request.note = "TEST-INSTRUCTIONS"
        res = self.report_obj._get_report_from_name(
            "base_maintenance.report_maintenance_request"
        )._render_qweb_text(generated_request.ids, False)
        self.assertRegex(str(res[0]), "TEST-INSTRUCTIONS")

    def test_maintenance_plan_button_manual_request_generation(self):
        self.assertEqual(len(self.maintenance_plan_1.maintenance_ids), 0)
        self.maintenance_plan_1.button_manual_request_generation()
        self.assertEqual(len(self.maintenance_plan_1.maintenance_ids), 3)
