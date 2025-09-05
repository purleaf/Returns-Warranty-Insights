list_1 = [1,2,3,4,5]
list_2 = [6,7,8,9,0]


###Variant 1
#Making a shallow copy list_1 to a new var and with for loop appending val one by one
#This method works but it `append`s each value one by one, so it's not very efficient`
joined_list = list_1[:]
for i in list_2:
    joined_list.append(i)
print(f"Variant 1: {joined_list}\noriginal list_1: {list_1}\noriginal list_2: {list_2}\n\n")

###Variant 2
#Creating new list by unpacking two lists in order
#This method is efficient and concise as it creates the exact list once
joined_list = [*list_1, *list_2]
print(f"Variant 2: {joined_list}\noriginal list_1: {list_1}\noriginal list_2: {list_2}\n\n")

###Variant 3
#Creating a shallow copy of the list_1 and inserting list_2 at it's tail
#This method works but it involves creating a shallow copy first and then extending it, so it's less efficient than Variant 2
joined_list = list(list_1)
joined_list[len(joined_list):] = list_2
print(f"Variant 3: {joined_list}\noriginal list_1: {list_1}\noriginal list_2: {list_2}")
