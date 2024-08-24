import logging
from abc import ABC
from typing import Any

logger = logging.getLogger(__name__)


class Pred(ABC):  # noqa: B024
    """
    Abstract base class for predictions of every task
    """

    def __init__(self, id: str, prediction: list[Any], context: str):
        self.id = id
        self.prediction = prediction
        self.context = context

    def to_json(self):
        raise NotImplementedError


class QACandidate:
    """
    A single QA candidate answer.
    """

    def __init__(
        self,
        answer_type: str,
        score: str,
        offset_answer_start: int,
        offset_answer_end: int,
        offset_unit: str,
        aggregation_level: str,
        probability: float = None,
        n_passages_in_doc: int = None,
        passage_id: str = None,
        confidence: float = None,
    ):
        """
        :param answer_type: The category that this answer falls into e.g. "no_answer", "yes", "no" or "span"
        :param score: The score representing the model's confidence of this answer
        :param offset_answer_start: The index of the start of the answer span (whether it is char or tok is stated in self.offset_unit)
        :param offset_answer_end: The index of the start of the answer span (whether it is char or tok is stated in self.offset_unit)
        :param offset_unit: States whether the offsets refer to character or token indices
        :param aggregation_level: States whether this candidate and its indices are on a passage level (pre aggregation) or on a document level (post aggregation)
        :param probability: The probability the model assigns to the answer
        :param n_passages_in_doc: Number of passages that make up the document
        :param passage_id: The id of the passage which contains this candidate answer
        :param confidence: The (calibrated) confidence score representing the model's predicted accuracy of the index of the start of the answer span
        """  # noqa: E501

        # self.answer_type can be "no_answer", "yes", "no" or "span"
        self.answer_type = answer_type
        self.score = score
        self.probability = probability

        # If self.answer_type is "span", self.answer is a string answer (generated by self.span_to_string())  # noqa: E501
        # Otherwise, it is None
        self.answer = None
        self.offset_answer_start = offset_answer_start
        self.offset_answer_end = offset_answer_end

        # If self.answer_type is in ["yes", "no"] then self.answer_support is a text string  # noqa: E501
        # If self.answer is a string answer span or self.answer_type is "no_answer", answer_support is None  # noqa: E501
        self.answer_support = None
        self.offset_answer_support_start = None
        self.offset_answer_support_end = None

        # self.context is the document or passage where the answer is found
        self.context_window = None
        self.offset_context_window_start = None
        self.offset_context_window_end = None

        # Offset unit is either "token" or "char"
        # Aggregation level is either "doc" or "passage"
        self.offset_unit = offset_unit
        self.aggregation_level = aggregation_level

        self.n_passages_in_doc = n_passages_in_doc
        self.passage_id = passage_id
        self.confidence = confidence

        # This attribute is used by Haystack to store sample metadata
        self.meta = None

    def set_context_window(self, context_window_size, clear_text):
        window_str, start_ch, end_ch = self._create_context_window(context_window_size, clear_text)  # noqa: E501
        self.context_window = window_str
        self.offset_context_window_start = start_ch
        self.offset_context_window_end = end_ch

    def set_answer_string(self, token_offsets, document_text):
        pred_str, self.offset_answer_start, self.offset_answer_end = self._span_to_string(token_offsets, document_text)  # noqa: E501
        self.offset_unit = "char"
        self._add_answer(pred_str)

    def _add_answer(self, string):
        """Set the answer string. This method will check that the answer given is valid given the start
        and end indices that are stored in the object."""  # noqa: E501
        if string == "":
            self.answer = "no_answer"
            if self.offset_answer_start != 0 or self.offset_answer_end != 0:
                logger.error(
                    f"Both start and end offsets should be 0: \n"
                    f"{self.offset_answer_start}, {self.offset_answer_end} with a no_answer. "  # noqa: E501
                )  # noqa: E501
        else:
            self.answer = string
            if self.offset_answer_end - self.offset_answer_start <= 0:
                logger.error(
                    f"End offset comes before start offset: \n"
                    f"({self.offset_answer_start}, {self.offset_answer_end}) with a span answer. "  # noqa: E501
                )  # noqa: E501
            elif self.offset_answer_end <= 0:
                logger.error(
                    f"Invalid end offset: \n" f"({self.offset_answer_start}, {self.offset_answer_end}) with a span answer. "  # noqa: E501
                )  # noqa: E501

    def _create_context_window(self, context_window_size, clear_text):
        """
        Extract from the clear_text a window that contains the answer and (usually) some amount of text on either
        side of the answer. Useful for cases where the answer and its surrounding context needs to be
        displayed in a UI. If the self.context_window_size is smaller than the extracted answer, it will be
        enlarged so that it can contain the answer

        :param context_window_size: The size of the context window to be generated. Note that the window size may be increased if the answer is longer.
        :param clear_text: The text from which the answer is extracted
        :return:
        """  # noqa: E501
        if self.offset_answer_start == 0 and self.offset_answer_end == 0:
            return "", 0, 0
        else:
            # If the extracted answer is longer than the context_window_size,
            # we will increase the context_window_size
            len_ans = self.offset_answer_end - self.offset_answer_start
            context_window_size = max(context_window_size, len_ans + 1)

            len_text = len(clear_text)
            midpoint = int(len_ans / 2) + self.offset_answer_start
            half_window = int(context_window_size / 2)
            window_start_ch = midpoint - half_window
            window_end_ch = midpoint + half_window

            # if we have part of the context window overlapping the start or end of the passage,  # noqa: E501
            # we'll trim it and use the additional chars on the other side of the answer
            overhang_start = max(0, -window_start_ch)
            overhang_end = max(0, window_end_ch - len_text)
            window_start_ch -= overhang_end
            window_start_ch = max(0, window_start_ch)
            window_end_ch += overhang_start
            window_end_ch = min(len_text, window_end_ch)
        window_str = clear_text[window_start_ch:window_end_ch]
        return window_str, window_start_ch, window_end_ch

    def _span_to_string(self, token_offsets: list[int], clear_text: str):
        """
        Generates a string answer span using self.offset_answer_start and self.offset_answer_end. If the candidate
        is a no answer, an empty string is returned

        :param token_offsets: A list of ints which give the start character index of the corresponding token
        :param clear_text: The text from which the answer span is to be extracted
        :return: The string answer span, followed by the start and end character indices
        """  # noqa: E501

        if self.offset_unit != "token":
            logger.error(
                f"QACandidate needs to have self.offset_unit=token before calling _span_to_string() (id = {self.id})"  # noqa: E501
            )  # noqa: E501

        start_t = self.offset_answer_start
        end_t = self.offset_answer_end

        # If it is a no_answer prediction
        if start_t == -1 and end_t == -1:
            return "", 0, 0

        n_tokens = len(token_offsets)

        # We do this to point to the beginning of the first token after the span instead of  # noqa: E501
        # the beginning of the last token in the span
        end_t += 1

        # Predictions sometimes land on the very final special token of the passage. But there are no  # noqa: E501
        # special tokens on the document level. We will just interpret this as a span that stretches  # noqa: E501
        # to the end of the document
        end_t = min(end_t, n_tokens)

        start_ch = int(token_offsets[start_t])
        # i.e. pointing at the END of the last token
        if end_t == n_tokens:  # noqa: SIM108
            end_ch = len(clear_text)
        else:
            end_ch = token_offsets[end_t]

        final_text = clear_text[start_ch:end_ch].strip()
        end_ch = int(start_ch + len(final_text))

        return final_text, start_ch, end_ch

    def add_cls(self, predicted_class: str):
        """
        Adjust the final QA prediction depending on the prediction of the classification head (e.g. for binary answers in NQ)
        Currently designed so that the QA head's prediction will always be preferred over the Classification head

        :param predicted_class: The predicted class e.g. "yes", "no", "no_answer", "span"
        """  # noqa: E501

        if predicted_class in ["yes", "no"] and self.answer != "no_answer":
            self.answer_support = self.answer
            self.answer = predicted_class
            self.answer_type = predicted_class
            self.offset_answer_support_start = self.offset_answer_start
            self.offset_answer_support_end = self.offset_answer_end

    def to_doc_level(self, start, end):
        """Populate the start and end indices with document level indices. Changes aggregation level to 'document'"""  # noqa: E501
        self.offset_answer_start = start
        self.offset_answer_end = end
        self.aggregation_level = "document"

    def to_list(self):
        return [
            self.answer,
            self.offset_answer_start,
            self.offset_answer_end,
            self.score,
            self.passage_id,
        ]  # noqa: E501


class QAPred(Pred):
    """A set of QA predictions for a passage or a document. The candidates are stored in QAPred.prediction which is a
    list of QACandidate objects. Also contains all attributes needed to convert the object into json format and also
    to create a context window for a UI
    """  # noqa: E501

    def __init__(
        self,
        id: str,
        prediction: list[QACandidate],
        context: str,
        question: str,
        token_offsets: list[int],
        context_window_size: int,
        aggregation_level: str,
        no_answer_gap: float,
        ground_truth_answer: str = None,
        answer_types: list[str] = [],  # noqa: B006
    ):  # noqa: B006
        """
        :param id: The id of the passage or document
        :param prediction: A list of QACandidate objects for the given question and document
        :param context: The text passage from which the answer can be extracted
        :param question: The question being posed
        :param token_offsets: A list of ints indicating the start char index of each token
        :param context_window_size: The number of chars in the text window around the answer
        :param aggregation_level: States whether this candidate and its indices are on a passage level (pre aggregation) or on a document level (post aggregation)
        :param no_answer_gap: How much the QuestionAnsweringHead.no_ans_boost needs to change to turn a no_answer to a positive answer
        :param ground_truth_answer: Ground truth answers
        :param answer_types: List of answer_types supported by this task e.g. ["span", "yes_no", "no_answer"]
        """  # noqa: E501
        super().__init__(id, prediction, context)
        self.question = question
        self.token_offsets = token_offsets
        self.context_window_size = context_window_size
        self.aggregation_level = aggregation_level
        self.answer_types = answer_types
        self.ground_truth_answer = ground_truth_answer
        self.no_answer_gap = no_answer_gap
        self.n_passages = self.prediction[0].n_passages_in_doc
        for qa_candidate in self.prediction:
            qa_candidate.set_answer_string(token_offsets, self.context)
            qa_candidate.set_context_window(self.context_window_size, self.context)

    def to_json(self, squad=False):
        """
        Converts the information stored in the object into a json format.

        :param squad: If True, no_answers are represented by the empty string instead of "no_answer"
        :return:
        """  # noqa: E501

        answers = self._answers_to_json(self.id, squad)
        ret = {
            "task": "qa",
            "predictions": [
                {
                    "question": self.question,
                    "id": self.id,
                    "ground_truth": self.ground_truth_answer,
                    "answers": answers,
                    "no_ans_gap": self.no_answer_gap,  # Add no_ans_gap to current no_ans_boost for switching top prediction  # noqa: E501
                }
            ],
        }
        if squad:
            del ret["predictions"][0]["id"]
            ret["predictions"][0]["question_id"] = self.id
        return ret

    def _answers_to_json(self, ext_id, squad=False):
        """
        Convert all answers into a json format

        :param id: ID of the question document pair
        :param squad: If True, no_answers are represented by the empty string instead of "no_answer"
        :return:
        """  # noqa: E501

        ret = []

        # iterate over the top_n predictions of the one document
        for qa_candidate in self.prediction:
            if squad and qa_candidate.answer == "no_answer":  # noqa: SIM108
                answer_string = ""
            else:
                answer_string = qa_candidate.answer
            curr = {
                "score": qa_candidate.score,
                "probability": None,
                "answer": answer_string,
                "offset_answer_start": qa_candidate.offset_answer_start,
                "offset_answer_end": qa_candidate.offset_answer_end,
                "context": qa_candidate.context_window,
                "offset_context_start": qa_candidate.offset_context_window_start,
                "offset_context_end": qa_candidate.offset_context_window_end,
                "document_id": ext_id,
            }
            ret.append(curr)
        return ret

    def to_squad_eval(self):
        return self.to_json(squad=True)
