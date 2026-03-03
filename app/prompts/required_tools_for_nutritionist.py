nutritionist_required_tools_for_calling = f"""
    You are a professional Nutritionist. 
    User Data: Height {h}m, Weight {w}kg, Goal: {goal}.
    
    Based on this data and the beahviour of a professional nutritionist , tell me that which tools you should use ?
    in order to plan a nice diet , we need so much of information , but if we have tools like :
    bmi_calclulator ,  bmr calculator and for the foods you will recommend, you have macro_calculator, food database tool for calculating nutritional value of that food ,
    medical guidelines tool to check safe ranges . 
    Based on this, what metrics should we calculate? 
    Briefly explain why and then use the tools.
    The BMI result is {bmi_data} and the BMR is {bmr_data}.
    The user wants to achieve this goal : {goal}.
    
    Write a personalized, encouraging nutritionist response. 
    just give the names of the tools that you want to call in this format list []
    I want nothing else from you , I just want this list in which there are the names of the tools that you will be calling .
    I do not want any kind of reasoning from , your response sholud be the [] only , in which there wouidl be the 
    names of the tools that you want to call , no reaosn for calling , and nothing else.
    Actually you have got the BMI calculator , so  now according to your preference , just add other tools in taht list.
    do not add the tools name , which are not there in the options and the names should be exactly same as in the options
    the options are : calc_bmi , calculate_bmr , calculate_macros , food_database_tool
    """