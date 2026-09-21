from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True, slots=True)
class DutyEntry:
    duty_date: date
    qq: int
    name: str

    def __post_init__(self) -> None:
        if not isinstance(self.duty_date, date):
            raise ValueError("值班日期无效")
        if not isinstance(self.qq, int) or isinstance(self.qq, bool) or self.qq <= 0:
            raise ValueError("QQ号必须是正整数")
        clean_name = self.name.strip()
        if not clean_name:
            raise ValueError("姓名不能为空")
        object.__setattr__(self, "name", clean_name)

    @classmethod
    def from_dict(cls, value: dict) -> "DutyEntry":
        try:
            duty_date = datetime.strptime(str(value["date"]), "%Y-%m-%d").date()
            qq = int(value["qq"])
            name = str(value["name"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"排班记录格式错误：{value!r}") from exc
        return cls(duty_date=duty_date, qq=qq, name=name)

    def to_dict(self) -> dict:
        return {"date": self.duty_date.isoformat(), "qq": self.qq, "name": self.name}


@dataclass(frozen=True, slots=True)
class Settings:
    robot_qq: int
    group_id: int
    send_time: str
    napcat_config: str

    def __post_init__(self) -> None:
        if self.robot_qq <= 0 or self.group_id <= 0:
            raise ValueError("机器人QQ和群号必须是正整数")
        try:
            datetime.strptime(self.send_time, "%H:%M")
        except ValueError as exc:
            raise ValueError("发送时间必须是 HH:MM 格式") from exc
        if not self.napcat_config.strip():
            raise ValueError("NapCat配置路径不能为空")

    @classmethod
    def from_dict(cls, value: dict) -> "Settings":
        try:
            return cls(
                robot_qq=int(value["robot_qq"]),
                group_id=int(value["group_id"]),
                send_time=str(value["send_time"]),
                napcat_config=str(value["napcat_config"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("设置文件缺少字段或字段无效") from exc

