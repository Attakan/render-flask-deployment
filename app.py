from flask import Flask, request, jsonify
from flask_cors import CORS, cross_origin
import os
import json
import traceback
from datetime import datetime, date
from werkzeug.utils import secure_filename

# Your DB connection helper
from config import create_db_connection

import mysql.connector  # or import from your config file

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def empty_string_to_none(s, default=None):
    return s if s != '' else default

def parse_date(s):
    if not s or s.strip() == "":
        return None
    
    try:
        # Try ISO format (YYYY-MM-DD)
        return datetime.strptime(s, '%Y-%m-%d').date()
    except ValueError:
        try:
            # Try alternate format (DD/MM/YYYY)
            return datetime.strptime(s, '%d/%m/%Y').date()
        except ValueError:
            # Additional debug info
            print(f"Could not parse date string: '{s}'")
            return None

def supplier_exists(supplier_code):
    connection = None
    cursor = None
    try:
        connection = create_db_connection()
        cursor = connection.cursor(dictionary=True)
        query = "SELECT supplier_name FROM supp_detail WHERE supplier_code = %s"
        cursor.execute(query, (supplier_code,))
        result = cursor.fetchone()
        return result['supplier_name'] if result else None
    except Exception as e:
        traceback.print_exc()
        return None
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

def plant_exists(plant_id):
    connection = None
    cursor = None
    try:
        connection = create_db_connection()
        cursor = connection.cursor(dictionary=True)
        query = "SELECT plant_id FROM hd_plant WHERE plant_id = %s"
        cursor.execute(query, (plant_id,))
        result = cursor.fetchone()
        return True if result else False
    except Exception as e:
        traceback.print_exc()
        return False
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

##############################################################################
# GET /sqcb - Only return non-deleted SQCB rows
##############################################################################
@app.route('/sqcb', methods=['GET'])
@cross_origin()
def get_all_sqcb():
    connection = None
    cursor = None
    try:
        connection = create_db_connection()
        cursor = connection.cursor(dictionary=True)
        sqcb_query = """
        SELECT
            sqcb_detail.id AS sqcb_id,
            sqcb_detail.sqcb,
            sqcb_detail.status,
            sqcb_detail.rqmr_no,
            sqcb_detail.disposition,
            sqcb_detail.plant_id,
            sqcb_detail.hd_incharge,
            sqcb_detail.sqcb_amount,
            sqcb_detail.feedback_date,
            sqcb_detail.target_date,
            sqcb_detail.rma_no,
            sqcb_detail.return_type,
            sqcb_detail.qm10_complete_date,
            sqcb_detail.dn_issued_date,
            sqcb_detail.scrap_week,
            sqcb_detail.po_no,
            sqcb_detail.obd_no,
            sqcb_detail.second_po_no,
            sqcb_detail.second_obd_no,
            sqcb_detail.comments,
            sqcb_detail.modified,
            supp_detail.supplier_code,
            supp_detail.supplier_name,
            user_detail.fullname AS created_by,
            user_detail.fullname AS modified_by
        FROM sqcb_detail
        LEFT JOIN supp_detail 
          ON sqcb_detail.supplier_code = supp_detail.supplier_code
        LEFT JOIN user_detail 
          ON sqcb_detail.hd_incharge = user_detail.fullname
        WHERE sqcb_detail.is_deleted = 0
        """
        cursor.execute(sqcb_query)
        sqcb_rows = cursor.fetchall()

        for sqcb in sqcb_rows:
            sqcb_number = sqcb['sqcb']
            # Fetch Parts
            parts_query = """
            SELECT
                notification_detail.item_number,
                notification_detail.notification_number,
                notification_detail.qty,
                part_detail.part_number,
                part_detail.part_name,
                COALESCE(
                    JSON_ARRAYAGG(
                        JSON_OBJECT(
                            'picture_name', picture.picture_name,
                            'picture_address', picture.picture_address
                        )
                    ), '[]'
                ) AS pictures
            FROM notification_detail
            LEFT JOIN part_detail 
              ON notification_detail.part_number = part_detail.part_number
            LEFT JOIN picture 
              ON notification_detail.notification_number = picture.notification_number
              AND picture.is_deleted = 0
            WHERE notification_detail.sqcb = %s
              AND notification_detail.is_deleted = 0
            GROUP BY
                notification_detail.item_number,
                notification_detail.notification_number,
                notification_detail.qty,
                part_detail.part_number,
                part_detail.part_name
            """
            cursor.execute(parts_query, (sqcb_number,))
            parts = cursor.fetchall()
            for part in parts:
                part['pictures'] = json.loads(part['pictures']) if part['pictures'] else []
            sqcb['parts'] = parts

            # Fetch Attachments
            attachments_query = """
            SELECT
                attachment_id, sqcb, attachment_item_id,
                attachment_name, attachment_address
            FROM attachments
            WHERE sqcb = %s
              AND is_deleted = 0
            """
            cursor.execute(attachments_query, (sqcb_number,))
            attachments = cursor.fetchall()
            sqcb['attachments'] = attachments

        return jsonify(sqcb_rows), 200

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

##############################################################################
# GET /suppliers/<supplier_code>
##############################################################################
@app.route('/suppliers/<supplier_code>', methods=['GET'])
@cross_origin()
def get_supplier_name(supplier_code):
    connection = None
    cursor = None
    try:
        connection = create_db_connection()
        cursor = connection.cursor(dictionary=True)
        query = "SELECT supplier_name FROM supp_detail WHERE supplier_code = %s"
        cursor.execute(query, (supplier_code,))
        result = cursor.fetchone()
        if result:
            return jsonify(result), 200
        else:
            return jsonify({"error": "Supplier not found"}), 404
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

##############################################################################
# GET /part/<part_number>
##############################################################################
@app.route('/part/<part_number>', methods=['GET'])
@cross_origin()
def get_part_info(part_number):
    connection = None
    cursor = None
    try:
        connection = create_db_connection()
        cursor = connection.cursor(dictionary=True)
        query = "SELECT part_number, part_name FROM part_detail WHERE part_number = %s"
        cursor.execute(query, (part_number,))
        result = cursor.fetchone()
        if result:
            return jsonify(result), 200
        else:
            return jsonify({"error": "Part not found"}), 404
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

##############################################################################
# POST /sqcb - Create a new SQCB
##############################################################################
@app.route('/sqcb', methods=['POST'])
@cross_origin()
def create_sqcb():
    connection = None
    cursor = None
    try:
        if 'sqcb' not in request.form:
            return jsonify({"error": "No SQCB data provided"}), 400

        data = request.form
        attachments_files = request.files.getlist('attachments')
        pictures_files = request.files.getlist('pictures')

        # Validate plant and supplier
        plant_id = data.get('plant_id')
        if not plant_id:
            return jsonify({"error": "plant_id is required"}), 400
        if not plant_exists(plant_id):
            return jsonify({"error": f"plant_id '{plant_id}' does not exist"}), 400

        supplier_code = data.get('supplier_code')
        if not supplier_code:
            return jsonify({"error": "supplier_code is required"}), 400
        supplier_name = supplier_exists(supplier_code)
        if not supplier_name:
            return jsonify({"error": f"supplier_code '{supplier_code}' not in supp_detail"}), 400

        connection = create_db_connection()
        cursor = connection.cursor()

        disposition_value = data.get('disposition') or 'WAITING FEEDBACK'
        sqcb_query = """
        INSERT INTO sqcb_detail (
            sqcb, status, rqmr_no, plant_id, hd_incharge, supplier_code, return_type,
            sqcb_amount, feedback_date, target_date, disposition, rma_no, qm10_complete_date,
            po_no, obd_no, dn_issued_date, scrap_week, second_po_no, second_obd_no, comments
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        sqcb_values = (
            data.get('sqcb'),
            data.get('status') or "Open",
            data.get('rqmr_no'),
            plant_id,
            data.get('hd_incharge'),
            supplier_code,
            empty_string_to_none(data.get('return_type')),
            empty_string_to_none(data.get('sqcb_amount')),
            parse_date(data.get('feedback_date')),
            parse_date(data.get('target_date')),
            disposition_value,
            empty_string_to_none(data.get('rma_no')),
            parse_date(data.get('qm10_complete_date')),
            empty_string_to_none(data.get('po_no')),
            empty_string_to_none(data.get('obd_no')),
            parse_date(data.get('dn_issued_date')),
            empty_string_to_none(data.get('scrap_week')),
            empty_string_to_none(data.get('second_po_no')),
            empty_string_to_none(data.get('second_obd_no')),
            data.get('comments', '') or None
        )
        cursor.execute(sqcb_query, sqcb_values)
        sqcb_id = cursor.lastrowid

        # Insert parts
        parts_data = data.get('parts')
        if parts_data:
            parts_data = json.loads(parts_data)
            for part in parts_data:
                notification_query = """
                INSERT INTO notification_detail (
                    notification_number, sqcb, item_number, qty, part_number
                )
                VALUES (%s, %s, %s, %s, %s)
                """
                notification_values = (
                    part.get('notification_number'),
                    data.get('sqcb'),
                    part.get('item_number'),
                    part.get('qty'),
                    part.get('part_number')
                )
                cursor.execute(notification_query, notification_values)
                part_query = """
                INSERT INTO part_detail (part_number, part_name)
                VALUES (%s, %s)
                ON DUPLICATE KEY UPDATE part_name=VALUES(part_name)
                """
                part_values = (
                    part.get('part_number'),
                    part.get('part_name')
                )
                cursor.execute(part_query, part_values)

        # Insert pictures
        if pictures_files:
            try:
                parts_data = json.loads(data.get('parts', '[]'))
                notification_number = parts_data[0].get('notification_number') if parts_data else None
                if not notification_number:
                    return jsonify({"error": "notification_number required for pictures"}), 400

                cursor.execute("SELECT COALESCE(MAX(picture_item_id), 0) FROM picture")
                current_max_id = cursor.fetchone()[0]

                for index, picture_file in enumerate(pictures_files, 1):
                    if picture_file and picture_file.filename and allowed_file(picture_file.filename):
                        new_id = current_max_id + index
                        picture_id = f"{notification_number}_{str(new_id).zfill(3)}"
                        filename = secure_filename(picture_file.filename)
                        unique_filename = f"{picture_id}_{filename}"
                        save_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
                        picture_file.save(save_path)
                        picture_query = """
                        INSERT INTO picture (
                            picture_id, notification_number, picture_item_id,
                            picture_name, picture_address
                        )
                        VALUES (%s, %s, %s, %s, %s)
                        """
                        picture_values = (
                            picture_id,
                            notification_number,
                            new_id,
                            filename,
                            save_path
                        )
                        cursor.execute(picture_query, picture_values)
            except Exception as e:
                connection.rollback()
                traceback.print_exc()
                return jsonify({"error": f"Failed to upload pictures: {str(e)}"}), 500

        # Insert attachments
        if attachments_files:
            try:
                cursor.execute("SELECT COALESCE(MAX(attachment_item_id), 0) FROM attachments")
                max_attachment_item_id = cursor.fetchone()[0]
                for attachment_file in attachments_files:
                    if attachment_file.filename:
                        max_attachment_item_id += 1
                        attachment_id = f"{data.get('sqcb')}_{str(max_attachment_item_id).zfill(3)}"
                        filename = secure_filename(attachment_file.filename)
                        save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                        attachment_file.save(save_path)
                        attachment_query = """
                        INSERT INTO attachments (
                            attachment_id, sqcb, attachment_item_id, 
                            attachment_name, attachment_address
                        )
                        VALUES (%s, %s, %s, %s, %s)
                        """
                        attachment_values = (
                            attachment_id,
                            data.get('sqcb'),
                            max_attachment_item_id,
                            filename,
                            save_path
                        )
                        cursor.execute(attachment_query, attachment_values)
            except Exception as e:
                connection.rollback()
                traceback.print_exc()
                return jsonify({"error": f"Failed to upload attachments: {str(e)}"}), 500

        connection.commit()
        return jsonify({"message": "SQCB created successfully", "sqcb_id": sqcb_id}), 201

    except Exception as e:
        traceback.print_exc()
        if connection:
            connection.rollback()
        return jsonify({"error": str(e)}), 400

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

##############################################################################
# PUT /sqcb/<id> - Update SQCB (preserve date fields if not provided)
##############################################################################
@app.route('/sqcb/<int:id>', methods=['PUT'])
@cross_origin()
def update_sqcb(id):
    connection = None
    cursor = None
    try:

        # Log the raw form data for debugging
        print("Raw form data received:")
        for key in request.form:
            print(f"  {key}: {request.form[key]}")

        data = request.form
        attachments_files = request.files.getlist('attachments')
        pictures_files = request.files.getlist('pictures')

        connection = create_db_connection()
        cursor = connection.cursor(dictionary=True)

        # Fetch existing record to preserve unchanged fields
        cursor.execute("SELECT * FROM sqcb_detail WHERE id=%s AND is_deleted=0", (id,))
        existing_data = cursor.fetchone()
        if not existing_data:
            return jsonify({"error": f"SQCB with ID {id} not found or is deleted"}), 404

        # Helper functions: if the new field value (after stripping) is empty, use existing_data's value.
        def get_value(field):
            new_val = data.get(field)
            if new_val is not None and new_val.strip() != "":
                return new_val
            else:
                return existing_data.get(field)

        def get_date_field(field):
            new_val = data.get(field)
            
            # Only process if we explicitly received a value
            if new_val is not None and new_val.strip() != "":
                try:
                    parsed_date = parse_date(new_val)
                    if parsed_date:
                        return parsed_date
                except Exception as e:
                    print(f"Date parsing failed for {field}: {str(e)}")
            
            # In all other cases, preserve the existing value
            return existing_data.get(field)

        update_query = """
        UPDATE sqcb_detail
        SET 
            sqcb=%s,
            status=%s,
            rqmr_no=%s,
            plant_id=%s,
            hd_incharge=%s,
            supplier_code=%s,
            return_type=%s,
            sqcb_amount=%s,
            feedback_date=%s,
            target_date=%s,
            disposition=%s,
            rma_no=%s,
            qm10_complete_date=%s,
            po_no=%s,
            obd_no=%s,
            dn_issued_date=%s,
            scrap_week=%s,
            second_po_no=%s,
            second_obd_no=%s,
            comments=%s
        WHERE id=%s
          AND is_deleted=0
        """
        update_values = (
            get_value('sqcb'),
            get_value('status'),
            get_value('rqmr_no'),
            get_value('plant_id'),
            get_value('hd_incharge'),
            get_value('supplier_code'),
            empty_string_to_none(get_value('return_type')),
            empty_string_to_none(get_value('sqcb_amount')),
            get_date_field('feedback_date'),
            get_date_field('target_date'),
            get_value('disposition'),
            empty_string_to_none(get_value('rma_no')),
            get_date_field('qm10_complete_date'),
            empty_string_to_none(get_value('po_no')),
            empty_string_to_none(get_value('obd_no')),
            get_date_field('dn_issued_date'),
            empty_string_to_none(get_value('scrap_week')),
            empty_string_to_none(get_value('second_po_no')),
            empty_string_to_none(get_value('second_obd_no')),
            get_value('comments'),
            id
        )
        cursor.execute(update_query, update_values)

        # Update Parts: Soft-delete old parts then insert new ones.
        parts_data = data.get('parts')
        if parts_data:
            parts_data = json.loads(parts_data)
            cursor.execute("UPDATE notification_detail SET is_deleted=1 WHERE sqcb = %s", (existing_data['sqcb'],))
            for part in parts_data:
                notification_query = """
                INSERT INTO notification_detail (
                    notification_number, sqcb, item_number, qty, part_number
                )
                VALUES (%s, %s, %s, %s, %s)
                """
                notification_values = (
                    part.get('notification_number'),
                    existing_data['sqcb'],
                    part.get('item_number'),
                    part.get('qty'),
                    part.get('part_number')
                )
                cursor.execute(notification_query, notification_values)
                part_query = """
                INSERT INTO part_detail (part_number, part_name)
                VALUES (%s, %s)
                ON DUPLICATE KEY UPDATE part_name=VALUES(part_name)
                """
                part_values = (part.get('part_number'), part.get('part_name'))
                cursor.execute(part_query, part_values)

        # Update Pictures: Soft-delete old ones and insert new
        if pictures_files:
            cursor.execute("""
                UPDATE picture
                SET is_deleted=1
                WHERE notification_number IN (
                    SELECT notification_number 
                    FROM notification_detail
                    WHERE sqcb = %s
                )
            """, (existing_data['sqcb'],))
            parts_data = json.loads(data.get('parts', '[]'))
            notification_number = parts_data[0].get('notification_number') if parts_data else None
            if notification_number:
                cursor.execute("SELECT COALESCE(MAX(picture_item_id), 0) FROM picture")
                current_max_id = cursor.fetchone()['COALESCE(MAX(picture_item_id), 0)']
                for index, picture_file in enumerate(pictures_files, 1):
                    if picture_file.filename and allowed_file(picture_file.filename):
                        new_id = current_max_id + index
                        picture_id = f"{notification_number}_{str(new_id).zfill(3)}"
                        filename = secure_filename(picture_file.filename)
                        unique_filename = f"{picture_id}_{filename}"
                        save_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
                        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
                        picture_file.save(save_path)
                        picture_query = """
                        INSERT INTO picture (
                            picture_id, notification_number, picture_item_id,
                            picture_name, picture_address
                        )
                        VALUES (%s, %s, %s, %s, %s)
                        """
                        picture_values = (
                            picture_id,
                            notification_number,
                            new_id,
                            filename,
                            save_path
                        )
                        cursor.execute(picture_query, picture_values)

        # Update Attachments
        if attachments_files:
            cursor.execute("UPDATE attachments SET is_deleted = 1 WHERE sqcb = %s", (existing_data['sqcb'],))
            cursor.execute("SELECT COALESCE(MAX(attachment_item_id), 0) AS maxId FROM attachments")
            attach_row = cursor.fetchone()
            max_attachment_item_id = attach_row['maxId'] if attach_row else 0
            for attachment_file in attachments_files:
                if attachment_file.filename:
                    max_attachment_item_id += 1
                    attachment_id = f"{existing_data['sqcb']}_{str(max_attachment_item_id).zfill(3)}"
                    filename = secure_filename(attachment_file.filename)
                    save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
                    attachment_file.save(save_path)
                    attachment_query = """
                    INSERT INTO attachments (
                        attachment_id, sqcb, attachment_item_id,
                        attachment_name, attachment_address
                    )
                    VALUES (%s, %s, %s, %s, %s)
                    """
                    attachment_values = (
                        attachment_id,
                        existing_data['sqcb'],
                        max_attachment_item_id,
                        filename,
                        save_path
                    )
                    cursor.execute(attachment_query, attachment_values)

        connection.commit()
        return jsonify({"message": "SQCB updated successfully"}), 200

    except Exception as e:
        traceback.print_exc()
        if connection:
            connection.rollback()
        return jsonify({"error": str(e)}), 400

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

##############################################################################
# DELETE /sqcb/<id> - Soft delete an entire SQCB
##############################################################################
@app.route('/sqcb/<int:id>', methods=['DELETE', 'OPTIONS'])
@cross_origin()
def soft_delete_sqcb(id):
    connection = None
    cursor = None
    try:
        connection = create_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT sqcb FROM sqcb_detail WHERE id = %s AND is_deleted=0", (id,))
        row = cursor.fetchone()
        if not row:
            return jsonify({"error": "SQCB not found or already deleted"}), 404

        sqcb_str = row['sqcb']
        cursor.execute("""
            UPDATE sqcb_detail
            SET is_deleted = 1,
                deleted_at = NOW()
            WHERE id = %s
        """, (id,))
        cursor.execute("""
            UPDATE attachments
            SET is_deleted = 1,
                deleted_at = NOW()
            WHERE sqcb = %s
        """, (sqcb_str,))
        cursor.execute("""
            UPDATE notification_detail
            SET is_deleted = 1,
                deleted_at = NOW()
            WHERE sqcb = %s
        """, (sqcb_str,))
        cursor.execute("""
            UPDATE picture
            SET is_deleted = 1,
                deleted_at = NOW()
            WHERE notification_number IN (
                SELECT notification_number
                FROM notification_detail
                WHERE sqcb = %s
            )
        """, (sqcb_str,))
        connection.commit()
        return jsonify({"message": "SQCB soft-deleted successfully"}), 200

    except Exception as e:
        traceback.print_exc()
        if connection:
            connection.rollback()
        return jsonify({"error": str(e)}), 400

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

@app.route('/attachments/<attachment_id>', methods=['DELETE', 'OPTIONS'])
@cross_origin()
def delete_attachment(attachment_id):
    connection = None
    cursor = None
    try:
        connection = create_db_connection()
        cursor = connection.cursor(dictionary=True)
        sql = """
            UPDATE attachments
            SET is_deleted = 1, deleted_at = NOW()
            WHERE attachment_id = %s
              AND is_deleted = 0
        """
        cursor.execute(sql, (attachment_id,))
        if cursor.rowcount == 0:
            return jsonify({"error": "Attachment not found or already deleted"}), 404
        connection.commit()
        return jsonify({"message": f"Attachment {attachment_id} deleted successfully"}), 200

    except Exception as e:
        traceback.print_exc()
        if connection:
            connection.rollback()
        return jsonify({"error": str(e)}), 500

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

##############################################################################
# GET /profile/<int:user_id>
##############################################################################
@app.route('/profile/<int:user_id>', methods=['GET'])
@cross_origin()
def get_profile(user_id):
    connection = None
    cursor = None
    try:
        connection = create_db_connection()
        cursor = connection.cursor(dictionary=True)
        sql = """
            SELECT 
                ud.user_id,
                ud.username,
                ud.name,
                ud.surname,
                ud.fullname,
                ud.job_description,
                ud.email,
                ud.supplier_code,
                ud.role,
                sd.supplier_name
            FROM user_detail ud
            LEFT JOIN supp_detail sd 
                ON ud.supplier_code = sd.supplier_code
            WHERE ud.user_id = %s
        """
        cursor.execute(sql, (user_id,))
        user = cursor.fetchone()
        if not user:
            return jsonify({"error": f"User with ID {user_id} not found"}), 404
        return jsonify(user), 200

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

@app.route('/profile/<int:user_id>', methods=['PUT'])
@cross_origin()
def update_profile(user_id):
    connection = None
    cursor = None
    try:
        data = request.json
        connection = create_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT user_id FROM user_detail WHERE user_id = %s", (user_id,))
        existing_user = cursor.fetchone()
        if not existing_user:
            return jsonify({"error": f"User with ID {user_id} not found"}), 404

        # Create base update fields list
        update_fields = [
            "username = %s",
            "name = %s",
            "surname = %s",
            "fullname = %s",
            "job_description = %s",
            "email = %s",
            "supplier_code = %s",
            "role = %s"
        ]
        
        # Start with base values
        update_values = [
            data.get('username', ''),            
            data.get('name', ''),
            data.get('surname', ''),
            data.get('fullname', ''),
            data.get('job_description', ''),
            data.get('email', ''),
            data.get('supplier_code', ''),
            data.get('role', ''),
        ]
        
        # Only include password_hash if it was provided
        password_hash = data.get('password_hash')
        if password_hash:
            update_fields.insert(1, "password_hash = %s")
            update_values.insert(1, password_hash)

        # Construct the final query
        sql = f"""
            UPDATE user_detail
            SET {", ".join(update_fields)}
            WHERE user_id = %s
        """
        
        # Add the user_id to the values list
        update_values.append(user_id)
        
        cursor.execute(sql, update_values)
        connection.commit()
        return jsonify({"message": "User profile updated successfully"}), 200

    except Exception as e:
        traceback.print_exc()
        if connection:
            connection.rollback()
        return jsonify({"error": str(e)}), 500

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

@app.route('/profile/<int:user_id>', methods=['DELETE'])
@cross_origin()
def delete_profile(user_id):
    connection = None
    cursor = None
    try:
        connection = create_db_connection()
        cursor = connection.cursor()
        cursor.execute("DELETE FROM user_detail WHERE user_id = %s", (user_id,))
        if cursor.rowcount == 0:
            return jsonify({"error": f"User with ID {user_id} not found"}), 404
        connection.commit()
        return jsonify({"message": "User profile deleted successfully"}), 200

    except Exception as e:
        traceback.print_exc()
        if connection:
            connection.rollback()
        return jsonify({"error": str(e)}), 500

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

##############################################################################
# POST /auth/login
##############################################################################
@app.route('/auth/login', methods=['POST'])
@cross_origin()
def login():
    connection = None
    cursor = None
    try:
        data = request.json
        username = data.get('username')
        password = data.get('password')

        if not username or not password:
            return jsonify({"error": "Username and password are required"}), 400

        connection = create_db_connection()
        cursor = connection.cursor(dictionary=True)

        user_query = """
            SELECT ud.user_id, ud.username, ud.password_hash, ud.name, 
                   ud.surname, ud.fullname, ud.job_description, ud.email,
                   ud.supplier_code, ud.role
            FROM user_detail ud
            WHERE ud.username = %s AND ud.password_hash = %s
        """
        cursor.execute(user_query, (username, password))
        user = cursor.fetchone()

        if not user:
            return jsonify({"error": "Invalid credentials"}), 401

        now = datetime.now()
        auth_query = """
            INSERT INTO user_authentication (user_id, password_hash, last_login)
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE
            password_hash = VALUES(password_hash),
            last_login = VALUES(last_login)
        """
        cursor.execute(auth_query, (user['user_id'], password, now))
        connection.commit()
        user.pop('password_hash', None)
        return jsonify({
            "message": "Login successful",
            "user": user,
            "last_login": now.strftime('%Y-%m-%d %H:%M:%S')
        }), 200

    except Exception as e:
        if connection:
            connection.rollback()
        print("Login error:", str(e))
        return jsonify({"error": "Login failed"}), 500

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

@app.route('/auth/logout', methods=['POST'])
@cross_origin()
def logout():
    try:
        user_id = request.json.get('user_id')
        if not user_id:
            return jsonify({"error": "User ID required"}), 400
        # Typically, invalidate session/token here
        return jsonify({"message": "Logout successful"}), 200

    except Exception as e:
        print("Logout error:", str(e))
        return jsonify({"error": "Logout failed"}), 500

##############################################################################
# GET /users
##############################################################################
@app.route('/users', methods=['GET'])
@cross_origin()
def get_all_users():
    connection = None
    cursor = None
    try:
        connection = create_db_connection()
        cursor = connection.cursor(dictionary=True)
        query = """
            SELECT user_id, username, password_hash, name, surname, fullname,
                   job_description, email, supplier_code, role
            FROM user_detail
        """
        cursor.execute(query)
        users = cursor.fetchall()
        return jsonify(users), 200

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

if __name__ == '__main__':
    app.run(debug=True, port=5000)
