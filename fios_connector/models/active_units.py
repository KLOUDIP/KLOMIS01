# -*- encoding: utf-8 -*-

import requests
import logging
from odoo import fields, models, _, api
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


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
    lot_id = fields.Many2one('stock.lot', string='Lot/Serial')

    def get_eid(self, token):
        """Get EID From API"""
        # get the response for extract eid number
        url = """http://sdk.kloudip.com/ajax.php?svc=token/login&params={"token":"%s","fl":1}""" % token
        try:
            response = requests.get(url).json()
        except:
            raise ValidationError(_('URL for get eid from FIOS API is incorrect!'))

        if 'error' in response:
            if response.get('error') == 7:
                raise UserError(_('FIOS Returned data with following error\n\nAccount is deactivated, please contact CMS administrator'))
            raise UserError(_('FIOS Returned data with following error\n\n\'%s\'. (Error code: \'%s\')') %
                            (response.get('reason'), response.get('error')))

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
            raise UserError(_('FIOS Returned data with an error(Error code: \'%s\')') % response.get('error'))

        return response

    def get_sync_key_record(self, item):
        """check sync-key field exist and get key of the field if exist"""
        try:
            return [x for x in item['aflds'] if item['aflds'][x]['n'] == 'sync-key']
        except KeyError as e:
            _logger.error('KeyError: %s ' % e)
            raise ValidationError('API token does not sent the sync field. (aflds field is missing in the API)')

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

    def get_fleet_vehicle(self, fios_item, sync_key):
        """Get available fleet vehicle belongs to FIOS nm"""
        # get the fleet vehicle belongs to vehicle license plate
        # |------------------------------------Domain-------------------------------------------|
        # |             FIOS                        Database            Status                  |
        # | 000002826384596867-MOBILE               6867-MOBILE         Will Load to Missing    |
        # |             65-263                        65-2639           Will Load to Missing    |
        # |-------------------------------------------------------------------------------------|
        # FIXME: loading MH-610 and MH-6106 both records when filtering
        fleet_vehicle = self.env['fleet.vehicle'].search([('license_plate', '!=', False)]).filtered(
            lambda z: ((z.license_plate in fios_item['nm']) or (fios_item['nm'] in z.license_plate) or
                       (z.license_plate == sync_key)) if sync_key != 'False'
            else ((z.license_plate in fios_item['nm']) or (fios_item['nm'] in z.license_plate)))

        if len(fleet_vehicle) > 1:
            # raise ValidationError(_('Multiple vehicles found with same plate number: \'%s\' \n\n FIOS \'nm\': \'%s\'') % (', '.join(fleet_vehicle.mapped('name')), str(fios_item['nm'])))
            # FIXME: remove indexing and get similar vehicle for the vehicle number
            # when search with the ilike(here 'in') conditions there will be multiple vehicles.
            # So we return [0] vehicle as fleet
            fleet_vehicle = fleet_vehicle[0]
            _logger.info(_('Multiple vehicles found with same plate number: \'%s\'. FIOS \'nm\': \'%s\'. Setting up the first vehicle that found as the vehicle.') % (', '.join(fleet_vehicle.mapped('name')), str(fios_item['nm'])))
        return fleet_vehicle

    def remove_matching_line_data(self, available_plates, available_sync_keys, matching_record, partner_id):
        """Remove matching line data (fios plate number, fios serial number)"""
        available_missing_recs = matching_record.mapped('matching_line_ids').filtered(lambda x: ((x.fios_plate_no.plate_no not in available_plates) if x.fios_plate_no else (x.fleet_vehicle_id.license_plate not in available_sync_keys)) and not x.removed_from_fios)
        if available_missing_recs:
            # update fields if the record is matched one
            update_recs = available_missing_recs.filtered(lambda x: x.serial_matched and x.plate_matched)
            # unlink missing fleets and missing serials
            update_recs.mapped('fios_plate_no').unlink()
            update_recs.mapped('fios_serial_no').unlink()
            update_recs.update({'fios_plate_no': False, 'fios_serial_no': False, 'removed_from_fios': True})
            # unlink the record if either serial or plate not matched--
            unlink_recs = available_missing_recs.filtered(lambda x: not x.serial_matched and not x.plate_matched)
            # unlink missing fleets and missing serials
            unlink_recs.mapped('fios_plate_no').unlink()
            unlink_recs.mapped('fios_serial_no').unlink()
            unlink_recs.unlink()
            # unmatch process for missing lines
            # update_recs.unmatch_vehicle()
            # update_recs.unmatch_serial()

    def get_active_units(self, env, response, eid):
        """Write necessary values to the system"""
        # create matching record to the partner if not exist
        matching_record = self.env['match.fios.missing'].search([('partner_id', '=', env.id)], limit=1)
        if not matching_record:
            matching_record = self.env['match.fios.missing'].create({'partner_id': env.id})

        active_units_data = []
        available_sync_keys = []
        available_plates = []
        for item in response.get('items'):
            if 'nm' and 'uid' in item:
                # get sync key record from response
                sync_key_rec = self.get_sync_key_record(item)
                # get sync_key
                sync_key = item['aflds'][sync_key_rec[0]]['v'] if len(sync_key_rec) == 1 else 'False'
                if sync_key != 'False':
                    available_sync_keys.append(sync_key)
                available_plates.append(item['nm'])

                # get fleet_vehicle
                fleet_vehicle = self.get_fleet_vehicle(item, sync_key)

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

                # Check item uid exist in FIOS. Raise error if uid not found
                if item['uid'] == '':
                    raise ValidationError(_('FIOS returned data with empty serial number for plate number - %s') % item['nm'])
                # get the serial for the api serial number
                lot_serial = self.env['stock.lot'].search(['|', ('name', 'ilike', item['uid']), ('fios_lot_no', '=', item['uid'])])
                # raise error when multiple lot/serials found
                if len(lot_serial) > 1:
                    raise ValidationError(_('Multiple Serials found for Serial Number \'%s\'. Either another serial assigned for the FIOS Serial Number - %s') % (lot_serial[0].name, item['uid']))
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
                matching_line_id = matching_record.matching_line_ids.search([('fios_plate_no', '=', missing_fleet_id.id)], limit=1) or matching_record.matching_line_ids.filtered(lambda x: x.fleet_vehicle_id.license_plate == sync_key)
                if not matching_line_id:
                    matching_record.matching_line_ids.create(matching_line_data)
                elif matching_line_id.removed_from_fios:
                    # check same serial or different serial received from fios
                    different_serial_received_from_fios = matching_line_id.different_serial_received_from_fios
                    matching_lot_id = matching_line_id.lot_id.id
                    if missing_serial_id.unit_serial != matching_line_id.lot_id.fios_lot_no:
                        different_serial_received_from_fios = True
                        # Modifications start here====================
                        # unlink fios missing serial
                        if missing_serial_id.id != matching_line_id.fios_serial_no.id:
                            matching_line_id.fios_serial_no.unlink()
                        # modifications end here =======================
                        # unmatch serial if different serial received
                        matching_line_id.unmatch_serial()
                        # check there is a serial created for missing serial, assign to matching line if so
                        matching_lot_id = self.env['stock.lot'].search([('name', '=', missing_serial_id.unit_serial)], limit=1).id
                    # update data to matching line
                    matching_line_id.update({
                        'fios_plate_no': missing_fleet_id.id,
                        'fios_serial_no': missing_serial_id.id,
                        'lot_id': matching_lot_id,
                        'different_serial_received_from_fios': different_serial_received_from_fios,
                        'removed_from_fios': False
                    })
                elif matching_line_id:
                    # check same serial or different serial received from fios
                    different_serial_received_from_fios = matching_line_id.different_serial_received_from_fios
                    matching_lot_id = matching_line_id.lot_id.id
                    if missing_serial_id.unit_serial != matching_line_id.lot_id.fios_lot_no and matching_line_id.serial_matched:
                        different_serial_received_from_fios = True
                        # Modifications start here
                        # unlink fios missing serial
                        if missing_serial_id.id != matching_line_id.fios_serial_no.id:
                            matching_line_id.fios_serial_no.unlink()
                        # Modifications end ====================
                        # unmatch serial if different serial received
                        matching_line_id.unmatch_serial()
                        # check there is a serial created for missing serial, assign to matching line if so
                        matching_lot_id = self.env['stock.lot'].search([('name', '=', missing_serial_id.unit_serial)], limit=1).id
                    # update data to matching line
                    matching_line_id.update({
                        'fios_plate_no': missing_fleet_id.id,
                        'fios_serial_no': missing_serial_id.id,
                        'lot_id': matching_lot_id,
                        'different_serial_received_from_fios': different_serial_received_from_fios,
                    })

                # compare api data and create active unit record for the selected customer or update the records
                # if exist
                # get fios updated fleet_vehicles and lot_serials
                fleet_vehicle = fleet_vehicle.filtered(lambda fleet: fleet.fios_plate_no_updated)
                lot_serial = lot_serial.filtered(lambda serial: serial.fios_lot_no)

                if fleet_vehicle and lot_serial:
                    # check with serial numbers and vehicle
                    contracts_with_serial_and_vehicle = self.env['fleet.vehicle.log.contract'].search([('vehicle_id', '=', fleet_vehicle.id), ('state', '!=', 'closed')]).filtered(lambda contract: contract.x_lot_id == lot_serial)
                    # check with partners
                    contracts = contracts_with_serial_and_vehicle.filtered(lambda y: y.partner_id.id == env.id)
                    active_units_data.append({
                        'fleet_vehicle_id': fleet_vehicle.id,
                        'lot_id': lot_serial.id,
                        'partner_id': env.id,
                        'unit_serial': item['uid'],
                        'plate_no': item['nm'],
                        'contract_ids': [(6, 0, contracts.ids)],
                        'contracts_empty': True if not contracts_with_serial_and_vehicle else False  # we need to check the fleet have any contracts with same serial otherwise show the create contract button
                    })
                    # update contract fios active units available field
                    contracts.update({'fios_active_unit_available': True})
        if active_units_data:
            for x in active_units_data:
                existing_active_unit = self.search([('partner_id', '=', x['partner_id']), '|', ('unit_serial', '=', x['unit_serial']), ('plate_no', '=', x['plate_no'])], limit=1)
                # create or update if exist
                if existing_active_unit:
                    existing_active_unit.write(x)
                else:
                    self.create([x])
        # update matching record last update status
        matching_record.update({'last_updated': fields.Datetime.now()})
        # remove matching lines if fios not returning the line that belongs to matching line
        self.remove_matching_line_data(available_plates, available_sync_keys, matching_record, env.id)
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
                'default_expiration_date': False,
                'add_vehicle_to_stock_move_line': 1,
                'default_x_lot_id': self.lot_id.id,
            },
        }
