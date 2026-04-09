"""演示 x.remove(2)：删除列表中第一个等于该值的元素"""

x = [1, 2, 3, 2, 3]

print("=" * 50)
print("初始 x =", x)
print("下标:      ", list(range(len(x))))
print()
print("x.remove(2) 会从前向后找，删除第一个 value == 2 的那一项，")
print("后面的其它 2 保留不动；该方法无返回值（不是 pop）。")
print()
first_idx = x.index(2)
print(f"第一个 2 出现的位置: index = {first_idx}（x[{first_idx}] == 2）")
x.remove(2)
print("执行 x.remove(2) 后 x =", x)
print("=" * 50)
