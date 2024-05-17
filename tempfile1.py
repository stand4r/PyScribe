keywords = {

}

for i, k in keywords.items():
    print(f'"{i}" :' + " {")
    for x in k:
        print("(r'" + r"\b" + x + r"\b'" + ", '#c77a5a'),", end=" ")
    print("}, ")
    print("")