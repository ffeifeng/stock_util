"""演示 aList[3:7] 的切片过程（Python 列表切片：左闭右开）"""

aList = [3, 4, 5, 6, 7, 9, 11, 13, 15, 17]

print("=" * 50)
print("原列表 aList:")
print(aList)
print()

# 索引与元素对应
print("下标（索引）与元素的对应关系:")
for i, v in enumerate(aList):
    print(f"  aList[{i}] = {v}")
print()

start, end = 3, 7
print(f"切片 aList[{start}:{end}] 的含义:")
print(f"  - 从索引 {start} 开始（包含）")
print(f"  - 到索引 {end} 结束（不包含），即实际取索引 {start}, {start+1}, ..., {end - 1}")
print()

included_indices = list(range(start, end))
print("参与切片的索引:", included_indices)
print("逐步取出:")
for idx in included_indices:
    print(f"  aList[{idx}] -> {aList[idx]}")
print()

result = aList[start:end]
print("切片结果（列表对象）:")
print(result)
print("=" * 50)
