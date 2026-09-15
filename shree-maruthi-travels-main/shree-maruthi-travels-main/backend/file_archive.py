"""Archive generated/uploaded files to Zoho WorkDrive and index them in Zoho Sheet."""
from datetime import datetime

import staff_auth


FILE_HEADERS = ('id', 'kind', 'filename', 'workdrive_id', 'permalink', 'uploaded_by', 'created_at', 'size')


def _who():
    staff = staff_auth.current_staff() or {}
    return staff.get('email') or 'staff'


def archive_bytes(kind, filename, content, uploaded_by=None):
    if not content:
        return {'ok': False, 'skipped': True, 'message': 'Empty file'}
    stamp = datetime.utcnow().strftime('%Y%m%d-%H%M%S')
    safe_name = f'{stamp}_{kind}_{filename}'.replace('/', '-').replace('\\', '-')
    try:
        import zoho_workdrive
        result = zoho_workdrive.upload_bytes(safe_name, content)
    except Exception as exc:
        print(f'[ARCHIVE] WorkDrive upload failed: {exc}')
        return {'ok': False, 'message': str(exc)}
    if not result.get('ok'):
        if not result.get('skipped'):
            print(f'[ARCHIVE] {result.get("message")}')
        return result
    row = {
        'id': stamp,
        'kind': kind,
        'filename': filename,
        'workdrive_id': result.get('id') or '',
        'permalink': result.get('permalink') or '',
        'uploaded_by': uploaded_by or _who(),
        'created_at': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
        'size': str(result.get('size') or len(content)),
    }
    try:
        from zoho_sheet import add_records, ensure_header_row, ensure_worksheet
        ensure_worksheet('SMT_Files')
        ensure_header_row('SMT_Files', list(FILE_HEADERS))
        add_records('SMT_Files', [row])
    except Exception as exc:
        print(f'[ARCHIVE] Sheet index failed: {exc}')
    return {**result, 'index': row}
