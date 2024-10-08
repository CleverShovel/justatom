class Question:
    def __init__(self, text: str, uid: str = None):
        self.text = text
        self.uid = uid

    def to_dict(self):
        ret = {"question": self.text, "id": self.uid, "answers": []}
        return ret


class QAInput:
    def __init__(self, doc_text: str, questions: list[Question] | Question):
        self.doc_text = doc_text
        if type(questions) == Question:  # noqa: E721
            self.questions = [questions]
        else:
            self.questions = questions

    def to_dict(self):
        questions = [q.to_dict() for q in self.questions]
        ret = {"qas": questions, "context": self.doc_text}
        return ret
