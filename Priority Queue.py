import heapq
from datetime import datetime, timedelta

class TopicNode:
    def __init__(self, topic_id, name):
        self.topic_id = topic_id
        self.name = name
        self.subtopics = []
        self.priority_queue = []  #(next_review_time, question_id)
        self.completed = False  #whether topic has been answered at least once

    def add_subtopic(self, subtopic_node):
        self.subtopics.append(subtopic_node)

    def add_question(self, question_id, next_review_time):
        heapq.heappush(self.priority_queue, (next_review_time, question_id))

    def pop_next_question(self):
        if self.priority_queue:
            return heapq.heappop(self.priority_queue)
        return None

    def is_soft_complete(self):
        if self.priority_queue:
            return False
        for sub in self.subtopics:
            if not sub.is_soft_complete():
                return False
        return True

    def reschedule_completed_questions(self, factor=2):
        new_queue = []
        for next_time, qid in self.priority_queue:
            new_time = datetime.now() + (next_time - datetime.now()) * factor
            heapq.heappush(new_queue, (new_time, qid))
        self.priority_queue = new_queue
