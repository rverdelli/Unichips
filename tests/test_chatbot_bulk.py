import unittest
from unittest.mock import patch

from modules.chatbot import init_state, process_message


COMPLETE_MAIL = """Da: Mario Rossi <mario.rossi@example.com>
Oggetto: Reclamo prodotto Classica

Buongiorno,
Nome: Mario Rossi
Prodotto: Classica
Codice lotto: LT12345
Scadenza: 10/2026
Punto vendita: Esselunga Milano
Descrizione: Ho aperto la confezione e ho trovato un frammento di plastica tra le patatine.

Cordiali saluti
Mario Rossi
"""

MISSING_LOT_MAIL = """Da: Laura Bianchi <laura.bianchi@example.com>
Oggetto: Segnalazione Rustica

Buongiorno,
Prodotto: Rustica
Punto vendita: Conad Roma
Descrizione: La confezione era sigillata ma le patatine erano tutte sbriciolate e in polvere.

Grazie
Laura Bianchi
"""

NO_NAME_MAIL = """Oggetto: Reclamo Classica

Buongiorno,
Email: cliente@example.com
Prodotto: Classica
Codice lotto: LT12345
Descrizione: Sono rimasta delusa perche' nella confezione ho trovato molte patatine bruciate.

Grazie
"""

CUSTOM_PRODUCT_MAIL = """Da: Mario Rossi <mario.rossi@example.com>
Oggetto: Reclamo prodotto Snack Test

Buongiorno,
Nome: Mario Rossi
Prodotto: Snack Test
Codice lotto: LT54321
Scadenza: 11/2026
Punto vendita: Coop Torino
Descrizione: Il prodotto aveva un odore anomalo appena aperta la confezione.

Grazie
Mario Rossi
"""


class ChatbotBulkComplaintTest(unittest.TestCase):
    def _state_with_photo(self):
        state = init_state()
        state["collected"]["has_photo"] = True
        return state

    def _run(self, message, state=None, config=None):
        classifier_result = {
            "cluster1": "CORPO ESTRANEO",
            "cluster2": "VARI",
            "gravity": "Alta",
            "priority": "Alta",
            "classification": "complesso",
            "status": "Aperto",
            "auto_response": False,
            "ai_response": "OK",
        }
        with patch("modules.chatbot.get_chatbot_config", return_value=config or {"clusters": []}), \
             patch("modules.llm.is_configured", return_value=False), \
             patch("modules.classifier.process_complaint", return_value=classifier_result), \
             patch("modules.chatbot.save_complaint", return_value=123) as save_complaint:
            reply, new_state, suggestions = process_message(message, state or init_state(), [])
        return reply, new_state, suggestions, save_complaint

    def test_complete_mail_from_welcome_is_saved_in_one_turn(self):
        _, state, _, save_complaint = self._run(COMPLETE_MAIL, self._state_with_photo())

        self.assertEqual(state["phase"], "done")
        self.assertEqual(state["complaint_id"], 123)
        self.assertEqual(state["collected"]["name"], "Mario Rossi")
        self.assertEqual(state["collected"]["email"], "mario.rossi@example.com")
        self.assertEqual(state["collected"]["product"], "Classica")
        self.assertEqual(state["collected"]["lot_code"], "LT12345")
        self.assertIn("frammento di plastica", state["collected"]["description"])
        save_complaint.assert_called_once()

    def test_complete_mail_without_photo_is_not_saved(self):
        reply, state, _, save_complaint = self._run(COMPLETE_MAIL)

        self.assertEqual(state["phase"], "collecting")
        self.assertEqual(state["waiting_for"], "photo")
        self.assertIn("foto", reply.lower())
        self.assertIsNone(state["complaint_id"])
        save_complaint.assert_not_called()

    def test_bulk_mail_while_waiting_for_name_does_not_store_raw_body_as_name(self):
        waiting_state = {
            "phase": "collecting",
            "collected": {"has_photo": True},
            "complaint_id": None,
            "waiting_for": "name",
        }

        _, state, _, _ = self._run(COMPLETE_MAIL, waiting_state)

        self.assertEqual(state["phase"], "done")
        self.assertEqual(state["collected"]["name"], "Mario Rossi")

    def test_incomplete_mail_collects_known_fields_and_asks_for_lot(self):
        _, state, _, save_complaint = self._run(MISSING_LOT_MAIL)

        self.assertEqual(state["phase"], "collecting")
        self.assertEqual(state["waiting_for"], "lot_code")
        self.assertEqual(state["collected"]["name"], "Laura Bianchi")
        self.assertEqual(state["collected"]["email"], "laura.bianchi@example.com")
        self.assertEqual(state["collected"]["product"], "Rustica")
        self.assertIn("sbriciolate", state["collected"]["description"])
        save_complaint.assert_not_called()

    def test_emotional_sentence_is_not_used_as_customer_name(self):
        _, state, _, save_complaint = self._run(NO_NAME_MAIL)

        self.assertEqual(state["phase"], "collecting")
        self.assertEqual(state["waiting_for"], "name")
        self.assertNotIn("name", state["collected"])
        self.assertEqual(state["collected"]["email"], "cliente@example.com")
        save_complaint.assert_not_called()

    def test_custom_configured_product_is_accepted(self):
        _, state, _, save_complaint = self._run(
            CUSTOM_PRODUCT_MAIL,
            self._state_with_photo(),
            config={"clusters": [], "products": ["Classica", "Snack Test"]},
        )

        self.assertEqual(state["phase"], "done")
        self.assertEqual(state["collected"]["product"], "Snack Test")
        save_complaint.assert_called_once()


if __name__ == "__main__":
    unittest.main()
