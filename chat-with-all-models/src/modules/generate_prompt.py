def generate_prompt(external_knowledge_access, enable_reference, user_system_prompt, knowledge, user_query):
    reference_instruction = ("\n.The knowledge base consist of 10 chunks. Each chunk has its metadata containing an `index` and a `url`.\n"
                                "1.Strictly format the references as `[index](url)` where `index` and `url` are retrieved from the "
                                "metadata of the chunk used for that part of the answer. \n**2.Strictly ensure the references are strictly placed"
                                " immediately after each relevant sentence or paragraph within the answer.**\n3.Strictly do not group"
                                " all the references at the end of the answer."
                                """ \n4.Examples for adding references are: If information for one sentence or paragraph in answer is used from chunk whose metadata is METADATA: { "index": 1, "pageNo": "36", "chunkNo": "1", "type": "file", "title": "Transformer architecture.pdf", "url": "knowledge-bases/slw6typk9aAGa8c6SEocHzEHAb6zWOHkiNyK5xjL.pdf" } then strictly write reference as [1](knowledge-bases/slw6typk9aAGa8c6SEocHzEHAb6zWOHkiNyK5xjL.pdf) at the end of that relevant sentence or paragraph of answer."""
                                """ and If information for other sentence or paragraph in same answer is from different chunk whose metadata is METADATA: { "index": 6, "pageNo": "1", "chunkNo": "8", "type": "audio", "title": "suno_bark small.wav", "url": "knowledge-bases/zBi7TlHUFQ8Nno3iOW3P1eoMIHwk9X4QMNHjA6a3.wav" } then strictly write reference as [6](knowledge-bases/zBi7TlHUFQ8Nno3iOW3P1eoMIHwk9X4QMNHjA6a3.wav) at the end of that relevant sentence or paragraph of answer""")

    if enable_reference:
        system_instructions = ("""You are an efficient response generator and efficient reference adder in the response. You have
                            been given with a query and information present in knowledge base and you need to generate  the answer
                            of the query. Must follow the markdown format. When asked about you then answer about yourself only as
                            per instructed here and do not use the knowledge base information here. """)

    else:
        system_instructions = ("""You are an efficient response generator. You have been given with a query and information present
                            in knowledge base and you need to generate  the answer of the query. Must follow the markdown format.
                            When asked about you then answer about yourself only as per instructed here and do not use the 
                            knowledge base information here. """)
    if external_knowledge_access and enable_reference:
        system_instructions += (
                           f"""\n1.You have to first strictly look into information in knowledge base and use that information to answer the
                           query. If information related to query is not present in knowledge base. Then only you use your own knowledge
                           to answer the query. \n2.**Add references at the end of parts of answer strictly for which you use information from
                           knowledge base and strictly Do not add reference for parts of answer for which you do not use information from 
                           knowledge base instead you use information from your own general knowledge.**. Do not add any reference if any information 
                           related to query is not present in knowledge base. Strictly strictly and force fully follow these instructions 
                           for format of references:\n{reference_instruction}""")
        user_query = ("Use information from knowledge base in answering the query. If information related to query present in knowledge base is not enough"
                      "to answer the query then"
                      "use your own knowledge to answer the query.Only add references for parts of the answer that use information from the knowledge base."
                      " Strictly Do not add references for parts based on general knowledge. If no relevant information is found in the knowledge base, strictly do not include any references in the answer, and avoid explicitly stating that no references were added."
                      f"**For format of references. Strictly follow instructions given to you.\n{reference_instruction}** \n\nThe query is:\n   {user_query}")
    if not external_knowledge_access and enable_reference:
        system_instructions += ("\n1.Just use information from given knowledge base to answer the query."
                                "If there is no information to the query in the given knowledge base information, "
                                "then strictly do not answer to the question even you know about the answer of that question."
                                "Your answer should be strictly: Unfortunately, I don't have the information necessary to answer"
                                " your question. Would you like to ask something else?\n2.Strictly add references in the answer by" 
                                f"following these instructions strictly:\n{reference_instruction}")
        user_query = (
            "Only use information from the given knowledge base to answer queries. If the knowledge base lacks relevant information, do not answer the question, even if you know the answer."
            f"**For format of references. Strictly follow instructions given to you.** \n\nThe query is:\n   {user_query}")

        if len(knowledge) == 0:
            return "Unfortunately, I don't have the information necessary to answer"
    if external_knowledge_access and not enable_reference:
        system_instructions += (
                           f"""\nYou have to first look into information in knowledge base and use that information to answer the
                           query. If information related to query is not present in knowledge base. Then you use your own knowledge
                           to answer the query.""")

    if not external_knowledge_access and not enable_reference:
        system_instructions += ("\n1.Just use information from given knowledge base to answer the query."
                                "If there is no information to the query in the given knowledge base information, "
                                "then strictly do not answer to the question even you know about the answer of that question."
                                "Your answer should be strictly: Unfortunately, I don't have the information necessary to answer"
                                " your question. Would you like to ask something else?")

        if len(knowledge) == 0:
            return "Unfortunately, I don't have the information necessary to answer"
    sep = "=" * 50
    system_instructions += f"\n {sep} \nKNOWLEDGE BASE:\n{knowledge}\n {sep}"

    msgs = [
        {'role': 'system', 'content': f"{user_system_prompt}\n\n{system_instructions}"}
    ]
    return msgs, user_query
