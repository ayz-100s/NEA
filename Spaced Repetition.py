from datetime import datetime, timedelta

class BaseSpacedRepition:
    def __init__(self, question_id, user_id):
        self.question_id = question_id
        self.user_id = user_id
        self.interval = 1.0           #days until next review
        self.ease_factor = 2.5        #factor of difficulty
        self.correct_streak = 0
        self.next_review_time = datetime.now()

    def UpdateReview(self, correct, time_taken=None):

        if correct:
            self.correct_streak += 1
        else:
            self.correct_streak = 0

        self.interval = max(1.0, self.interval)
        self.next_review_time = datetime.now() + timedelta(days=self.interval)

    def ReviewTime(self):
        return self.next_review_time



class FSRS(BaseSpacedRepition):
    def UpdateReview(self, correct, time_taken=None):

        if correct:
            self.correct_streak += 1
            self.ease_factor += 0.1  #slightly easier
        else:
            self.correct_streak = 0
            self.ease_factor = max(1.3, self.ease_factor - 0.2)

        # FSRS interval calculation
        if self.correct_streak == 1:
            self.interval = 1
        elif self.correct_streak == 2:
            self.interval = 6
        else:
            self.interval = self.interval * self.ease_factor

        if time_taken:
            self.interval *= max(0.9, min(1.1, 10 / (time_taken + 1))) #bad if takes too long

        self.next_review_time = datetime.now() + timedelta(days=self.interval)



