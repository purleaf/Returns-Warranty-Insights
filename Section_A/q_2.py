def convert_to_base_10(input_val: tuple):
    bases = {"binary" : 2, "octal" : 8,"decimal" : 10, "hex" : 16} #Dict with available bases types
    number, base_type = input_val
    base_type = base_type.lower()
    if base_type not in bases: #Checking if base is in available
        return "ValueError"
    base = bases[base_type] #Assining int representation for the base
    number = number.upper() #Normalizing number

    final = 0

    #Separating whole part of the number and decimal place
    if "." in number:
        splitted_n = number.split(".")
        whole, places = splitted_n
    else:
        whole = number
        places = None

    rev_whole = whole[::-1] #Reversing the whole part of the number to start converting

    def digitise_number(n: str) -> int:
        if n.isdigit():
            return int(n)
        else: #Checking the char into digital form
            return 10 + ord(n) - ord("A") #Digitizing to decimal by converting every char to unicode


    #Now converting the whole part of the number
    for i in range(len(rev_whole)):
        if digitise_number(rev_whole[i]) >= base: #Checking if the digit is smaller then base
            return "ValueError"
        else:
            final += digitise_number(rev_whole[i])*pow(base, i) #Converting to decimal in accordance with the rule
    if places: #Converting the number places
        for i in range(len(places)):
            if digitise_number(places[i]) > base:
                return "ValueError"
            else:
                final += digitise_number(places[i])*pow(base, -(i+1))

    return final
test = [("101.11", "binary"),
        ("174", "octal"),
        ("1FA.A", "hex"),
        ("121.456", "decimal")]

for example in test:
    print(convert_to_base_10(example))
