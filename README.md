# 本地支出记录工具

使用 Python 3 标准库和 SQLite 记录个人支出，支持查看、筛选、分类汇总、按 ID 删除和导出 CSV。

## 环境准备

- Python 3.8 或更高版本。
- 不需要安装第三方 Python 包，也不需要网络或外部 API。
- 在项目根目录（包含 `expense_tracker` 文件夹的目录）运行命令。

## 数据库路径

默认数据库为项目根目录下的 `expenses.db`。使用全局参数 `--db PATH` 可以指定其他 SQLite 文件；相对路径以当前工作目录为基准，不存在的数据库父目录会自动创建。全局参数放在子命令之前：

```text
python -m expense_tracker --db ./data/personal.db add 2026-10-09 交通 12.00
python -m expense_tracker --db ./data/personal.db list
python -m expense_tracker --db ./data/personal.db summary
```

应用会直接增量读写现有数据库，不会为新增功能重建数据库或清除已有记录。

## 新增支出

```text
python -m expense_tracker add YYYY-MM-DD 分类 金额 [--note 备注]
```

示例：

```text
python -m expense_tracker add 2026-10-09 餐饮 36.50 --note "午餐"
```

成功后显示新记录的整数 ID。日期必须是有效的 `YYYY-MM-DD` 日历日期；分类会去掉首尾空白，去除后不能为空；金额必须是大于零的普通十进制数，最多两位小数。备注可以省略或留空，并支持中文。

## 查看记录

```text
python -m expense_tracker list [--start-date YYYY-MM-DD] [--end-date YYYY-MM-DD] [--category 分类]
```

示例：

```text
python -m expense_tracker list --start-date 2026-10-01 --end-date 2026-10-31
python -m expense_tracker list --category 餐饮
python -m expense_tracker list --start-date 2026-10-01 --category 餐饮
```

起止日期都包含当天；可以只提供其中一端。多个筛选条件同时使用时，记录必须全部符合。分类按文字精确匹配，首尾空白会先去除。无筛选参数时，命令保持显示全部记录的原有行为。记录按日期升序排列，同一天按 ID 升序排列；无匹配记录时显示“暂无支出记录。”

日期格式无效、起始日期晚于结束日期或分类为空时，会输出错误并以非零状态退出。

## 分类汇总

```text
python -m expense_tracker summary [--start-date YYYY-MM-DD] [--end-date YYYY-MM-DD] [--category 分类]
```

示例：

```text
python -m expense_tracker summary --start-date 2026-10-01 --end-date 2026-10-31 --category 餐饮
```

筛选规则与 `list` 相同。分类合计和全部支出的总金额都只基于符合条件的记录；金额以元为单位显示两位小数。无匹配记录时会显示“暂无支出记录。”，总金额为 `0.00`。不提供筛选参数时，汇总全部记录。

## 删除记录

```text
python -m expense_tracker delete ID
```

示例：

```text
python -m expense_tracker delete 12
```

ID 必须是正整数。命令直接删除指定记录，不要求交互确认；删除成功会显示 ID。ID 格式非法或记录不存在时会显示错误并以非零状态退出，其他记录不受影响。删除结果保存在 SQLite 数据库中。

## 导出 CSV

```text
python -m expense_tracker export --output PATH
```

示例：

```text
python -m expense_tracker export --output ./exports/expenses.csv
```

导出全部记录，按日期升序、同一天按 ID 升序排列。CSV 固定使用 `id,date,category,amount,note` 表头；金额以元为单位保留两位小数。文件使用带 BOM 的 UTF-8 编码，分类或备注中的中文、逗号、双引号和换行会按 CSV 格式转义。

输出文件的父目录必须已经存在。若目标文件已存在，程序拒绝覆盖并以非零状态退出，保留原文件内容；目录不存在或文件无法写入时也会报告错误并以非零状态退出。空数据库会生成只有表头的 CSV。导出不会更改支出记录。

## 错误与测试

无效日期、分类、金额或 ID，反向日期范围，不存在的待删除 ID，以及导出路径错误都会产生简明错误并以非零状态退出。无效新增输入不会新增记录。

在项目根目录运行标准库测试：

```text
python -m unittest discover -v
```
