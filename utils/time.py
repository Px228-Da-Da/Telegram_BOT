import time
import datetime
import pytz

from config import TIMEZONE

tz = pytz.timezone(TIMEZONE)

def now_ts() -> int:
    return int(time.time())

def to_ts(dt: datetime.datetime) -> int:
    return int(dt.replace(tzinfo=pytz.UTC).timestamp())

def from_ts(ts: int) -> datetime.datetime:
    return datetime.datetime.fromtimestamp(ts, tz=pytz.UTC)

def humanize_ts(ts: int) -> str:
    dt = from_ts(ts).astimezone(tz)
    return dt.strftime("%Y-%m-%d %H:%M")
