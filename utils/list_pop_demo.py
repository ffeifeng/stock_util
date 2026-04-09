"""演示 x.pop()：无参数时弹出并返回最后一个元素"""

x = [1, 2, 3, 2, 3]

print("=" * 50)
print("初始 x =", x)
print("len(x) =", len(x))
print("最后一个元素下标:", len(x) - 1, "-> x[-1] =", x[-1])
print()
print("x.pop() 含义：不传索引时，删除并返回列表末尾一项。")
removed = x.pop()
print("返回值（被弹出的元素）:", removed)
print("执行后 x =", x)
print("=" * 50)
