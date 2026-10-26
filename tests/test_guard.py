import unittest

from owe.guard import invented_facts, review


SOURCE = (
    "Hey — are you still coming Saturday? Priya said you might bring the speaker. "
    "Let me know by tonight, otherwise I'll ask Jordan."
)


class GuardTests(unittest.TestCase):
    def test_holding_reply_can_send_when_model_agrees(self) -> None:
        result = review(
            {
                "reply": "Thanks for checking. I will confirm about Saturday and the speaker tonight.",
                "must_not_invent": "Whether you are coming, and whether you have the speaker.",
                "can_send": True,
                "why": "The reply only promises a confirmation that the message already asked for.",
            },
            SOURCE,
        )
        self.assertTrue(result["can_send"])
        self.assertEqual(result["blocked"], [])
        self.assertLessEqual(result["word_count"], 60)

    def test_invented_time_is_blocked(self) -> None:
        result = review(
            {
                "reply": "Yes, I will be there at 7 with the speaker.",
                "must_not_invent": "The arrival time.",
                "can_send": True,
                "why": "Looks ready.",
            },
            SOURCE,
        )
        self.assertFalse(result["can_send"])
        self.assertTrue(any("7" in issue for issue in result["blocked"]))

    def test_invented_name_is_blocked(self) -> None:
        self.assertIn("Alex", invented_facts("Ask Alex to cover the speaker.", SOURCE))

    def test_names_from_the_message_are_allowed(self) -> None:
        self.assertEqual(invented_facts("I will tell Jordan and Priya tonight.", SOURCE), [])

    def test_note_facts_count_as_source(self) -> None:
        result = review(
            {
                "reply": "I can't come Saturday, but I can drop the speaker with Priya tonight.",
                "must_not_invent": "What time tonight the drop-off would be.",
                "can_send": True,
                "why": "The decision is already in the note.",
            },
            SOURCE + "\nI can't come Saturday, but I can drop the speaker with Priya tonight.",
        )
        self.assertTrue(result["can_send"])

    def test_over_long_reply_is_blocked(self) -> None:
        reply = " ".join(["word"] * 61)
        result = review(
            {
                "reply": reply,
                "must_not_invent": "Whether you are coming.",
                "can_send": True,
                "why": "Too long.",
            },
            SOURCE,
        )
        self.assertFalse(result["can_send"])
        self.assertEqual(result["word_count"], 61)

    def test_placeholder_missing_fact_is_rewritten_when_the_reply_is_clean(self) -> None:
        result = review(
            {
                "reply": "I can't come Saturday, but I can drop the speaker with Priya tonight.",
                "must_not_invent": "None",
                "can_send": True,
                "why": "The note already decided it.",
            },
            SOURCE + "\nI can't come Saturday, but I can drop the speaker with Priya tonight.",
        )
        self.assertTrue(result["can_send"])
        self.assertNotEqual(result["must_not_invent"], "None")
        self.assertIn("does not add a fact", result["must_not_invent"])

    def test_instruction_echo_is_rewritten(self) -> None:
        result = review(
            {
                "reply": "I can't come Saturday, but I can drop the speaker with Priya tonight.",
                "must_not_invent": "the reply uses only facts already written above.",
                "can_send": True,
                "why": "The note already decided it.",
            },
            SOURCE + "\nI can't come Saturday, but I can drop the speaker with Priya tonight.",
        )
        self.assertTrue(result["can_send"])
        self.assertIn("does not add a fact", result["must_not_invent"])

    def test_empty_missing_fact_is_blocked(self) -> None:
        result = review(
            {"reply": "Thanks, I will reply tonight.", "must_not_invent": "  ", "can_send": True, "why": ""},
            SOURCE,
        )
        self.assertFalse(result["can_send"])


if __name__ == "__main__":
    unittest.main()
