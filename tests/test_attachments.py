import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from modules import database


class AttachmentPersistenceTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.patches = [
            patch.object(database, "DB_PATH", root / "complaints.db"),
            patch.object(database, "UPLOAD_ROOT", root / "uploads"),
        ]
        for p in self.patches:
            p.start()
        database.init_db()

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        self.tmp.cleanup()

    def test_pending_attachment_can_be_linked_to_complaint(self):
        attachment_id = database.save_attachment_record(
            session_id="sess_test",
            complaint_id=None,
            original_filename="foto.png",
            stored_path="pending/sess_test/foto.png",
            content_type="image/png",
            size_bytes=1234,
        )

        pending = database.get_pending_attachments("sess_test")
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]["id"], attachment_id)

        complaint_id = database.save_complaint({
            "name": "Mario Rossi",
            "email": "mario@example.com",
            "product": "Classica",
            "problem_category": "Patatina bruciata",
            "description": "Patatine bruciate nella confezione.",
            "lot_code": "LT12345",
            "status": "Aperto",
            "classification": "complesso",
        })

        database.attach_pending_attachment(
            attachment_id,
            complaint_id,
            f"complaints/{complaint_id}/foto.png",
        )

        complaint = database.get_complaint_by_id(complaint_id)
        attachments = database.get_complaint_attachments(complaint_id)

        self.assertEqual(complaint["has_photo"], 1)
        self.assertEqual(len(attachments), 1)
        self.assertEqual(attachments[0]["original_filename"], "foto.png")
        self.assertEqual(attachments[0]["stored_path"], f"complaints/{complaint_id}/foto.png")


if __name__ == "__main__":
    unittest.main()
