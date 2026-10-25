# ==============================================================================
# _queue.py - Queue Manager
# ==============================================================================
# In-memory queues for all chats. It manages what's currently playing and 
# what's up next using fast double-ended queues.
# ==============================================================================

from collections import defaultdict, deque
from typing import Union

from ._dataclass import Media, Track

# MediaItem can be either a Media or Track object
MediaItem = Union[Media, Track]


class Queue:
    def __init__(self):
        # Dictionary mapping chat_id to its queue (deque of Media/Track items)
        # defaultdict automatically creates a new deque for new chat_ids
        self.queues: dict[int, deque[MediaItem]] = defaultdict(deque)
        self.history: dict[int, list[MediaItem]] = defaultdict(list)

    def add(self, chat_id: int, item: MediaItem) -> int:
        self.queues[chat_id].append(item)  # Add to end of queue
        return len(self.queues[chat_id]) - 1  # Return position (0-based index)

    def check_item(self, chat_id: int, item_id: str) -> tuple[int, MediaItem | None]:
        pos, track = next(
            (
                (i, track)
                for i, track in enumerate(list(self.queues[chat_id]))
                if track.id == item_id
            ),
            (-1, None),
        )
        return pos, track

    def force_add(
        self, chat_id: int, item: MediaItem, remove: int | bool = False
    ) -> None:
        if remove is False:
            self.queues[chat_id].appendleft(item)
        else:
            self.remove_current(chat_id)
            self.queues[chat_id].appendleft(item)
            if remove is not True:
                # If remove is an integer representing position
                self.queues[chat_id].rotate(-remove)
                self.queues[chat_id].popleft()
                self.queues[chat_id].rotate(remove)

    def get_current(self, chat_id: int) -> MediaItem | None:
        return self.queues[chat_id][0] if self.queues[chat_id] else None

    def get_next(self, chat_id: int, check: bool = False) -> MediaItem | None:
        if not self.queues[chat_id]:
            return None
        if check:
            return self.queues[chat_id][1] if len(self.queues[chat_id]) > 1 else None

        popped_item = self.queues[chat_id].popleft()
        self.history[chat_id].append(popped_item)
        return self.queues[chat_id][0] if self.queues[chat_id] else None

    def get_previous(self, chat_id: int) -> MediaItem | None:
        if not self.history[chat_id]:
            return None
        
        # Pop from history and prepend to queue
        prev_item = self.history[chat_id].pop()
        
        # Current playing item becomes the "next" item (index 1)
        self.queues[chat_id].appendleft(prev_item)
        return prev_item

    def get_queue(self, chat_id: int) -> list[MediaItem]:
        return list(self.queues[chat_id])
    
    def get_all(self, chat_id: int) -> list[MediaItem]:
        return self.get_queue(chat_id)

    def remove_current(self, chat_id: int) -> None:
        if self.queues[chat_id]:
            self.history[chat_id].append(self.queues[chat_id].popleft())

    def requeue_history(self, chat_id: int) -> None:
        # Move already played items back into the queue (used by queue loop mode)
        self.queues[chat_id].extend(self.history[chat_id])
        self.history[chat_id].clear()

    def clear(self, chat_id: int) -> None:
        self.queues[chat_id].clear()
        self.history[chat_id].clear()

    def peek_next(self, chat_id: int, count: int = 2) -> list[MediaItem]:
        if not self.queues[chat_id] or len(self.queues[chat_id]) <= 1:
            return []
        
        # Convert deque to list and skip first item (currently playing)
        queue_list = list(self.queues[chat_id])
        return queue_list[1:min(len(queue_list), count + 1)]
    
    @staticmethod
    def is_downloaded(item: MediaItem) -> bool:
        return bool(getattr(item, 'file_path', None))
