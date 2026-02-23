import os
import json
import uuid
import logging

POLLS_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "polls.json")

class PollManager:
    def __init__(self):
        self.polls = self._load()

    def _load(self):
        if not os.path.exists(POLLS_FILE):
            return {}
        try:
            with open(POLLS_FILE, "r") as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"Failed to load polls: {e}")
            return {}

    def _save(self):
        try:
            os.makedirs(os.path.dirname(POLLS_FILE), exist_ok=True)
            with open(POLLS_FILE, "w") as f:
                json.dump(self.polls, f, indent=4)
        except Exception as e:
            logging.error(f"Failed to save polls: {e}")

    def create_poll(self, creator_id: str, question: str, options: list) -> str:
        poll_id = str(uuid.uuid4())[:6]  # short ID
        self.polls[poll_id] = {
            "creator": creator_id,
            "question": question,
            "options": {str(i+1): opt.strip() for i, opt in enumerate(options)},
            "votes": {},  # user_id -> option_number
            "active": True
        }
        self._save()
        return poll_id

    def vote(self, user_id: str, poll_id: str, option: str) -> str:
        if poll_id not in self.polls:
            return f"Poll '{poll_id}' not found."
        poll = self.polls[poll_id]
        if not poll["active"]:
            return f"Poll '{poll_id}' is closed."
        if option not in poll["options"]:
            return f"Invalid option. Available options: {', '.join(poll['options'].keys())}"
        
        poll["votes"][user_id] = option
        self._save()
        return f"Voted for '{poll['options'][option]}' on poll '{poll_id}'."

    def close_poll(self, user_id: str, poll_id: str) -> str:
        if poll_id not in self.polls:
            return f"Poll '{poll_id}' not found."
        poll = self.polls[poll_id]
        # Allow creator or "local_user" to close
        if poll["creator"] != user_id and user_id != "local_user":
            return "Only the creator can close this poll."
            
        poll["active"] = False
        self._save()
        return f"Poll '{poll_id}' closed."

    def get_results(self, poll_id: str) -> str:
        if poll_id not in self.polls:
            return f"Poll '{poll_id}' not found."
        poll = self.polls[poll_id]
        
        status = "Active" if poll["active"] else "Closed"
        lines = [f"📊 **Poll {poll_id}** ({status})", f"**{poll['question']}**"]
        
        # Tally
        counts = {opt_num: 0 for opt_num in poll["options"].keys()}
        for user, opt in poll["votes"].items():
            if opt in counts:
                counts[opt] += 1
                
        total_votes = max(1, len(poll["votes"]))
        
        for num, text in poll["options"].items():
            c = counts[num]
            bar = "█" * int((c / total_votes) * 10)
            lines.append(f"{num}. {text}: {c} vote(s) {bar}")
            
        return "\n".join(lines)
