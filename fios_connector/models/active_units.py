# -*- encoding: utf-8 -*-

from odoo import api, fields, models, _
import requests
from odoo.exceptions import UserError, ValidationError
from dateutil import tz
from datetime import datetime


class ActiveUnits(models.Model):
    _name = 'active.units'
    _description = 'Active Units'
    _rec_name = 'plate_no'

    unit_serial = fields.Char(string='Unit Serial')
    plate_no = fields.Char(string='Plate Number')
    contract_ids = fields.Many2many('fleet.vehicle.log.contract', 'fleet_contracts', string='Fleet Contracts')
    partner_id = fields.Many2one('res.partner', string='Partner')
    contracts_empty = fields.Boolean(string='Contracts Empty', help='For UI Purposes')
    fleet_vehicle_id = fields.Many2one('fleet.vehicle', string='Fleet Vehicle')
    sync_key = fields.Char(string='Sync-Key', related='fleet_vehicle_id.license_plate', help='FIOS API Sync-Key (Also equal to vehicle plate number)')
    lot_id = fields.Many2one('stock.production.lot', string='Lot/Serial')

    def get_eid(self, token):
        """Get EID From API"""
        # get the response for extract eid number
        url = """http://sdk.kloudip.com/ajax.php?svc=token/login&params={"token":"%s","fl":1}""" % token
        response = requests.get(url).json()

        if 'error' in response:
            raise UserError(_('FIOS Returned with following error\n\n\'%s\'. (Error code \'%s\')') % (
                response.get('reason'), response.get('error')))

        # get the eid number
        eid = response.get('eid')
        return eid

    def get_response_from_fios_api(self, eid):
        """Get data from API"""
        # get response with normal fields
        # url = """http://sdk.kloudip.com/ajax.php?svc=core/search_items&params={"spec":{"itemsType":"avl_unit","propName":"","propValueMask":"*","sortType":""},"force":1,"flags":257,"from":0,"to":0}&sid=%s&reportTemplate""" % eid
        # get response with admin fields (only difference in "flags": 385 url)
        url = """http://sdk.kloudip.com/ajax.php?svc=core/search_items&params={"spec":{"itemsType":"avl_unit","propName":"","propValueMask":"*","sortType":""},"force":1,"flags":385,"from":0,"to":0}&sid=%s&reportTemplate""" % eid
        response = requests.get(url).json()

        if 'error' in response:
            raise UserError(_('FIOS Returned data with an error(Error code \'%s\')') % response.get('error'))

        return response

    def get_sync_key_record(self, item):
        """check sync-key field exist and get key of the field if exist"""
        return [x for x in item['aflds'] if item['aflds'][x]['n'] == 'sync-key']

    # update/create sync-key field to FIOS
    def update_create_sync_key(self, item, sync_key_rec, licence_plate, eid):
        """Update Or create sync_key in API"""
        # update values if the field exist
        if len(sync_key_rec) == 1 and item['aflds'][sync_key_rec[0]]['v'] != licence_plate:
            item_id, ref_id, call_mode, field_val = item['id'], sync_key_rec[0], 'update', licence_plate
        # create field and values if the field not exist
        elif len(sync_key_rec) == 0:
            item_id, ref_id, call_mode, field_val = item['id'], 1, 'create', licence_plate
        # raise error if multiple fields found
        elif len(sync_key_rec) > 1:
            raise ValidationError(_('Multiple Sync-Key fields found for ItemID: %s. Please contact your '
                                    'system administrator!') % item['id'])
        else:  # condition will here if item['aflds'][sync_key_rec[0]]['v'] == licence_plate
            return True
        # create url for update or create sync-key field
        url = ("""http://sdk.kloudip.com/ajax.php?svc=item/update_admin_field&params={"itemId":%s,"id":%s,"callMode":"%s","n":"sync-key","v":"%s"}&sid=%s""") % (str(item_id), str(ref_id), call_mode, str(field_val), eid)
        response = requests.get(url).json()
        return response  # return is unnecessary

    def get_active_units(self, env, response, eid):
        """Write necessary values to the system"""
        # create matching record to the partner if not exist
        matching_record = self.env['match.fios.missing'].search([('partner_id', '=', env.id)], limit=1)
        if not matching_record:
            matching_record = self.env['match.fios.missing'].create({'partner_id': env.id})
        active_units_data = []
        for item in response.get('items'):
            if 'nm' and 'uid' in item:
                # get sync key record from response
                sync_key_rec = self.get_sync_key_record(item)
                # make domain if sync_key_rec exist
                domain = ['|',  ('license_plate', 'ilike', item['nm']), ('license_plate', '=', item['aflds'][sync_key_rec[0]]['v'])] if len(sync_key_rec) == 1 else [('license_plate', 'ilike', item['nm'])]
                # get vehicle
                fleet_vehicle = self.env['fleet.vehicle'].search(domain)  # get the fleet vehicle belongs to vehicle license plate

                # raise error when multiple fleet vehicles found
                if len(fleet_vehicle) > 1:
                    raise ValidationError(_('Multiple vehicles found for number plate \'%s\'') % item['nm'])

                # check missing_fleets available for the fleet by comparing licence plate
                missing_fleets_obj = self.env['missing.fleets']
                missing_fleet_id = missing_fleets_obj.search([('plate_no', '=', item['nm'])])
                # create missing fleet record if fleet vehicle not find in the system
                if not missing_fleet_id:
                    missing_fleet_id = missing_fleets_obj.create({
                        'partner_id': env.id,
                        'plate_no': item['nm'],
                        'item_id': item['id']
                    })

                # get the serial for the api serial number
                lot_serial = self.env['stock.production.lot'].search(['|', ('name', 'ilike', item['uid']), ('fios_lot_no', '=', item['uid'])])
                # raise error when multiple lot/serials found
                if len(lot_serial) > 1:
                    raise ValidationError(_('Multiple Serials found for Serial Number \'%s\'') % item['uid'])
                # check serial availability in system
                missing_serial_obj = self.env['missing.serial']
                missing_serial_id = missing_serial_obj.search([('unit_serial', '=', item['uid'])])
                if not missing_serial_id:
                    missing_serial_id = missing_serial_obj.create({
                        'partner_id': env.id,
                        'unit_serial': item['uid'],
                    })
                # write data to the matching lines
                matching_line_data = {
                        'match_fios_missing_id': matching_record.id,
                        'fios_plate_no': missing_fleet_id.id,
                        'fleet_vehicle_id': fleet_vehicle.id if fleet_vehicle else False,
                        'fios_serial_no': missing_serial_id.id,
                        'lot_id': lot_serial.id if lot_serial else False
                    }
                matching_line_id = matching_record.matching_line_ids.search([('fios_plate_no', '=', missing_fleet_id.id)], limit=1)
                if not matching_line_id:
                    matching_record.matching_line_ids.create(matching_line_data)
                # else:
                #     matching_line_id.update(matching_line_data)

                # compare api data and create active unit record for the selected customer or update the records
                # if exist
                # get fios updated fleet_vehicles and lot_serials
                fleet_vehicle = fleet_vehicle.filtered(lambda fleet: fleet.fios_plate_no_updated)
                lot_serial = lot_serial.filtered(lambda serial: serial.fios_lot_no)

                if fleet_vehicle and lot_serial:
                    contracts = self.env['fleet.vehicle.log.contract'].search([('vehicle_id', '=', fleet_vehicle.id), ('partner_id', '=', env.id), ('state', '!=', 'closed')])
                    # check with serial numbers
                    # contracts = contracts.filtered(lambda contract: contract.x_studio_lot_id == lot_serial).ids
                    contracts = contracts.filtered(lambda contract: contract.x_lot_id == lot_serial).ids  # TODO: Enable this when move to production
                    active_units_data.append({
                        'fleet_vehicle_id': fleet_vehicle.id,
                        'lot_id': lot_serial.id,
                        'partner_id': env.id,
                        'unit_serial': item['uid'],
                        'plate_no': item['nm'],
                        'contract_ids': [(6, 0, contracts)],
                        'contracts_empty': True if not contracts else False
                    })
        if active_units_data:
            for x in active_units_data:
                existing_active_unit = self.search([('partner_id', '=', x['partner_id']), '|', ('unit_serial', '=', x['unit_serial']), ('plate_no', '=', x['plate_no'])], limit=1)
                # create or update if exist
                if existing_active_unit:
                    existing_active_unit.write(x)
                else:
                    self.create([x])
        # update matching record last update status
        # matching_record.update({'last_updated': fields.Datetime.now().replace(tzinfo=tz.tzutc()).astimezone(tz.gettz(self.env.context.get('tz')))})
        matching_record.update({'last_updated': fields.Datetime.now()})
        return True

    def create_fleet_contracts(self):
        """Open create Contract with default context"""
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'fleet.vehicle.log.contract',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_vehicle_id': self.fleet_vehicle_id.id,
                'default_partner_id': self.partner_id.id,
                # 'default_x_studio_lot_id': self.lot_id.id,
                'default_x_lot_id': self.lot_id.id,  # TODO:Enable when move to production
            },
        }
