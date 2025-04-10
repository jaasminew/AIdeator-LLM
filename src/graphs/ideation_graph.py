from typing import TypedDict, Annotated, Sequence, List, Dict, Optional
from langgraph.graph import Graph, StateGraph
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI
import os 
from dotenv import load_dotenv
import json
import re

load_dotenv()

# Define the state with more detailed information
class IdeationState(TypedDict):
    messages: Sequence[HumanMessage | AIMessage | SystemMessage]
    feedback: str
    context: Dict[str, str]
    problem_statement: str
    problem_statement_2: str  # Renamed from refined_problem_statement to problem_statement_2
    final_problem_statement: str  # Track the final selected problem statement
    waiting_for_input: bool
    awaiting_choice: bool  # Track if we're waiting for user to choose between statements
    input_instructions: Dict[str, str]  # Instructions for UI/CLI on what inputs to collect
    regenerate_problem_statement_1: bool  # Flag to indicate regeneration of problem_statement_1
    regenerate_problem_statement_2: bool  # Flag to indicate regeneration of problem_statement_2
    
    # New fields for exploration options
    threads: Dict[str, Dict]  # Store the three exploration approaches
    active_thread: Optional[str]  # Track the selected exploration approach
    awaiting_thread_choice: bool  # Track if we're waiting for user to choose an exploration approach
    mindmap: Dict  # For future mindmap structure
    current_step: str  # Track current step in workflow
    
    # New fields for concept expansion
    branches: Dict[str, Dict]  # Store all branches with unique indices
    active_branch: Optional[str]  # Track the currently selected branch
    awaiting_branch_choice: bool  # Track if we're waiting for branch selection
    branch_counter: int  # Global counter for branch indices
    awaiting_concept_input: bool  # Track if we're waiting for user input for concept expansion
    concept_expansion_context: Dict  # Context for concept expansion

# Initialize the LLM
llm = ChatOpenAI(
    model="gpt-3.5-turbo",
    temperature=0.7,
    api_key=os.getenv("OPENAI_API_KEY")
)

# Define the system message template
SYSTEM_TEMPLATE = """Persona: You are an extremely creative entrepreneur with a proven track record of developing innovative, profitable products. As my co-founder and ideation partner, your primary mission is to empower me to generate my own high-quality ideas. Rather than simply listing products or solutions, focus on supporting my brainstorming process by offering strategic questions, frameworks, and prompts that spark unconventional thinking. Challenge my assumptions, introduce fresh perspectives, and guide me to explore new angles—while letting me take the lead in discovering the possibilities.

Goal: In this session, we will co-create a brainstorming mindmap focused on a single problem statement at the center. Together, we'll explore and expand on interconnected concepts, directions, and ideas branching out from that central theme. By combining and refining the various elements in the mindmap, we will ultimately arrive at a set of well-defined product concepts."""

# Define the prompt template for problem statement generation
PROBLEM_STATEMENT_PROMPT = ChatPromptTemplate.from_messages([
    SystemMessage(content=SYSTEM_TEMPLATE),
    ("human", """Generate a single-sentence problem statement for:
Target Audience: {target_audience}
Problem: {problem}

Your response must be:
1. A single sentence starting with "How might we"
2. Include the target audience and problem
3. Include the preferred outcome of the solution in the end
4. End with a question mark
5. No longer than 20 words
6. No additional text or explanations

Example:
Input: Target Audience: college students, Problem: difficulty connecting with industry professionals
Output: "How might we facilitate meaningful connections between college students and industry professionals to enable early exploration of career paths and informed decision-making?"

Now generate a problem statement for:
Target Audience: {target_audience}
Problem: {problem}""")
])

# Define the NEW prompt template for problem statement refinement
PROBLEM_REFINEMENT_PROMPT = ChatPromptTemplate.from_messages([
    SystemMessage(content=SYSTEM_TEMPLATE),
    ("human", """Please follow these steps to generate an alternative problem statement (problem_statement_2) based on this original problem statement:
"{problem_statement}"

1. Identify the Current Problem Statement
   - Write down the original statement.

2. Extract the Preferable Outcome
   - Ask yourself: "After this problem is solved, what do we want to see happening? What's the ideal situation or behavior?"
   - Write this down as your `preferable_outcome`.

3. Brainstorm an Alternate Way to Achieve the Same Outcome
   - Think of another method or approach that would also fulfill the `preferable_outcome`.

4. Create a Second Problem Statement, and form `problem_statement_2`
   - Using the alternate approach, form another "How might we…" statement:
     "How might we + [alternate method] + [preferable_outcome]?"

5. **Output Requirement:**
   - Output only the `problem_statement_2` (the newly formed "How might we…" statement), as a single sentence.
   - Do not include any explanation or additional text.
   - No longer than 20 words.""")
])

# Template for "Emotional Root Causes" exploration - placeholder for future implementation
EMOTIONAL_ROOT_CAUSES_PROMPT = ChatPromptTemplate.from_messages([
    SystemMessage(content=SYSTEM_TEMPLATE),
    MessagesPlaceholder(variable_name="thread_messages"),
    ("human", """Please follow these steps to explore the emotional root causes behind {problem_statement}. Return only valid JSON in the exact structure specified below. Use concise phrasing (one or two sentences per field). 
a. Emotional Seeds
1. Task: Identify 3 core emotional root causes leading to the problem. What feelings (e.g., anxiety, longing, excitement) do people experience? Why do these emotions arise?
2. Add-on: For each root cause, suggest one product direction that addresses or harnesses the emotion to improve the user experience.
3. Tip: Seek genuinely empathetic insights. Consider social context, personal identity, and psychological triggers. Avoid generic or superficial explanations.

b. Habit & Heuristic Alignment
1. Task: List 2 key human habits or heuristics relevant to the domain (e.g., preference for consistency, aversion to steep learning curves, love for quick feedback).
2. Add-on: Brainstorm 1 direction that cleverly leverages or strengthens these habits.
3. Tip: Think beyond the obvious. Explore how established routines, comfort zones, or mental shortcuts can be nudged in creative ways to improve engagement and satisfaction.

c. Delightful Subversion
1. Task: Identify 2 commonly negative or taboo perceptions/frustrations in this context.
2. Add-on: Suggest how each could be flipped into something playful, intriguing, or surprisingly positive. Keep suggestions concise and open-ended.
3. Tip: Push your creativity here! Consider surprise-and-delight mechanics, or turning negative emotions into rewards that reshape the user's emotional journey.

Please follow this example of valid output:
{{
  "emotionalSeeds": [
    {{
      "heading": "Fear of letting others down",
      "explanation": "Social and professional pressures can make people fear judgment from peers.",
      "productDirection": "Use progress-sharing with supportive feedback loops instead of performance scores."
    }}
  ],
  "habitHeuristicAlignment": [
    {{
      "heading": "Preference for social proof",
      "explanation": "People tend to feel safer engaging when they see others like them participating.",
      "productDirection": "Showcase student testimonials and photos of real cultural meetups to spark FOMO-driven curiosity."
    }}
  ],
  "delightfulSubversion": [
    {{
      "heading": "Fear of making social mistakes",
      "explanation": "Missteps in unfamiliar social norms can cause embarrassment or withdrawal.",
      "productDirection": "Gamify social learning with humorous 'oops cards' that turn faux pas into laughable, teachable moments."
    }}
  ]
}}""")
])

# Template for "Unconventional Associations" exploration - placeholder for future implementation
UNCONVENTIONAL_ASSOCIATIONS_PROMPT = ChatPromptTemplate.from_messages([
    SystemMessage(content=SYSTEM_TEMPLATE),
    MessagesPlaceholder(variable_name="thread_messages"),
    ("human", """Please follow these steps to explore the unconventional associations behind {problem_statement}. Please return only valid JSON in the exact structure specified below. Use concise phrasing (one or two sentences per field). 

a. Attribute-Based Bridging
Identify Attributes: Choose 3 defining attributes or characteristics of the problem concept (e.g., "it requires active maintenance," "it thrives on collaboration," or "it's quick to appear but slow to sustain").
Cross-Domain Link: For each attribute, select one concept from a completely different field—technology, biology, art, history, sports, etc.—that also exhibits or relies on this same attribute.
Insight & Product Direction: Explain how the unexpected link can spark new understanding or design ideas for the problem. Propose one product direction based on this analogy.
     
b. Broader Domains
Explore from 2 different perspectives (eg. psychologist, historian, poet, child, philosopher). Feel free to adapt or replace these perspectives to suit the context. Under each perspective, summarize their core concepts as headings, and then describe how each uniquely interprets the problem.
For each perspective, propose one idea or feature that draws inspiration from that viewpoint.
     
c. Metaphorical Links
Present 2 conceptual or symbolic metaphors that could reframe the problem on psychological, spiritual, emotional, or other layers.
Summarize the metaphor and provide one feature or design suggestion that arises from it.
Please follow this example of valid output:
{{
  "attributeBasedBridging": [
    {{
      "heading": "Maintains Momentum (Sailing a Boat)",
      "explanation": "Both focus and sailing require active navigation of changing conditions to stay on course.",
      "productDirection": "Implement a 'drift alert' that nudges users when they stray from tasks, suggesting immediate refocus strategies."
    }}
  ],
  "broaderDomains": [
    {{
      "heading": "Cognitive load affecting concentration",
      "explanation": "Psychologists explore cognitive load and how stress levels affect sustained concentration over time.",
      "productDirection": "Include periodic check-ins for emotional wellbeing, offering calming exercises before focus-intensive tasks."
    }}
  ],
  "metaphoricalLinks": [
    {{
      "heading": "Focus as a Muscle",
      "explanation": "It strengthens with repetition but requires rest and recovery to grow effectively.",
      "productDirection": "Provide a 'cooldown timer' suggesting short breaks after intense work sessions to prevent fatigue."
    }}
  ]
}}""")
])

# Template for "Imaginary Customers' Feedback" exploration - placeholder for future implementation
IMAGINARY_FEEDBACK_PROMPT = ChatPromptTemplate.from_messages([
    SystemMessage(content=SYSTEM_TEMPLATE),
    MessagesPlaceholder(variable_name="thread_messages"),
    ("human", """Please follow these steps to explore the unconventional associations behind {problem_statement}. Please return only valid JSON in the exact structure specified below. Use concise phrasing (one or two sentences per field).
a. Create 4 Imaginary Target Users & Their Feedback
Invent Personas: Come up with 4 distinct user profiles, each having a short description (e.g., name, age, occupation). Making sure they are differentiated enough.
Background: Write one sentence summarizing the persona's daily life, habits, and tech savviness.
Feedback: List one struggle, pain point, or initial thought the persona might have about the problem as the heading. Ensure each pain point reflects a distinct perspective—mental, physical, emotional, etc.—and is not overlapping. Then, explain this pain point in a single concise sentence.

b. Respond with Potential Product Directions
Link to Feedback: For each feedback item, propose a concise product direction that addresses or alleviates the user's struggle.
Practical Innovations: Focus on new features, design improvements, or creative innovations that respond to the user's specific needs or pain points.

Please follow this example of valid output:
[
  {{
    "heading": "Notifications are very distracting.",
    "userProfile": "Emma, 26, Remote Designer. Works from coffee shops, juggling multiple freelance clients and productivity tools.",
    "feedback": [
      {{
        "explanation": "I can get distracted by notifications from different platforms fairly easy",
        "productDirection": "Implement an automatic 'focus mode' that silences unrelated notifications during task time."
      }}
    ]
  }}
 ]""")
])

# New template for concept expansion
CONCEPT_EXPANSION_PROMPT = ChatPromptTemplate.from_messages([
    SystemMessage(content=SYSTEM_TEMPLATE),
    ("human", """The problem statement we are trying to solve is: {problem_statement}. {context}, I want to further explore and expand on this concept: {concept_to_expand}

Here's the prompt: {user_guidance} Based on the prompt, please provide 3 potential directions of this concept. 

Please return only valid JSON without any extra text or explanation. Format your response as JSON with these sections:
[
{{
  "heading": "Expanded concept name",
  "explanation": "Deeper analysis of the concept",
  "productDirection": "description of the product concept"
}}""")
])

# New function for concept expansion with default guidance
DEFAULT_GUIDANCE_PROMPT = ChatPromptTemplate.from_messages([
    SystemMessage(content=SYSTEM_TEMPLATE),
    ("human", """Please generate the most relevant and simplest one-sentence question to this concept: {concept_to_expand} that would help expand this single concept into more branches. The output should only include the question, no other text or explanation. Do not include "gamification" or anything related in your answer.
Good example: What are some typical forms of Fear of Missing Out (FOMO)?""")
])

def request_input(state: IdeationState) -> IdeationState:
    """Prepare state for human input by specifying what input is needed."""
    # Set up instructions in the state about what inputs we need to collect
    # This makes the function interface-agnostic - any UI can read these instructions
    state["input_instructions"] = {
        "target_audience": "Target audience:",
        "problem": "Problem:"
    }
    
    state["waiting_for_input"] = True
    state["awaiting_choice"] = False
    state["regenerate_problem_statement_1"] = False
    state["regenerate_problem_statement_2"] = False
    state["current_step"] = "initial_input"
    
    # Initialize branch-related fields
    state["branches"] = {}
    state["branch_counter"] = 0
    state["active_branch"] = None
    state["awaiting_branch_choice"] = False
    state["awaiting_concept_input"] = False
    state["concept_expansion_context"] = {}
    
    return state

def generate_problem_statement(state: IdeationState) -> IdeationState:
    """Generate a problem statement based on target audience and problem."""
    # Validate required inputs
    if not state["context"].get("target_audience") or not state["context"].get("problem"):
        state["problem_statement"] = "Error: Missing required inputs. Please provide both target audience and problem."
        return state

    try:
        # Create the prompt with target audience and problem
        prompt = PROBLEM_STATEMENT_PROMPT.format_messages(
            target_audience=state["context"]["target_audience"],
            problem=state["context"]["problem"]
        )
        
        # Generate response
        response = llm.invoke(prompt)
        formatted_response = response.content.strip()
        
        # Update state with response
        state["problem_statement"] = formatted_response
        
        # If this is the initial generation or a regeneration
        if not any(msg.content.startswith("Statement 1:") for msg in state["messages"] if isinstance(msg, AIMessage)):
            state["messages"].append(AIMessage(content=f"Statement 1: {formatted_response}"))
        else:
            # Replace the existing Statement 1 message
            for i, msg in enumerate(state["messages"]):
                if isinstance(msg, AIMessage) and msg.content.startswith("Statement 1:"):
                    state["messages"][i] = AIMessage(content=f"Statement 1: {formatted_response}")
                    break
        
        state["waiting_for_input"] = False
        state["regenerate_problem_statement_1"] = False
        state["current_step"] = "generate_problem_statement_2"
        
        return state

    except Exception as e:
        state["problem_statement"] = f"Error generating problem statement: {str(e)}"
        return state

def generate_problem_statement_2(state: IdeationState) -> IdeationState:
    """Generate an alternative problem statement (problem_statement_2)."""
    if not state.get("problem_statement"):
        state["problem_statement_2"] = "Error: No problem statement to work with."
        return state

    try:
        # Create prompt with the current problem statement
        prompt = PROBLEM_REFINEMENT_PROMPT.format_messages(
            problem_statement=state["problem_statement"]
        )
        
        # Generate response
        response = llm.invoke(prompt)
        problem_statement_2 = response.content.strip()
        
        # Post-process to extract just the "How might we" statement if there's extra content
        if len(problem_statement_2.split('\n')) > 1 or len(problem_statement_2.split('.')) > 1:
            import re
            hmw_statements = re.findall(r"How might we[^.?!]*[.?!]", problem_statement_2)
            if hmw_statements:
                problem_statement_2 = hmw_statements[-1].strip()  # Take the last one as it's likely the final statement
        
        # Store the second problem statement
        state["problem_statement_2"] = problem_statement_2
        
        # Only append to messages if it's not a regeneration or if messages doesn't already contain Statement 2
        if not state["regenerate_problem_statement_2"] or not any(msg.content.startswith("Statement 2:") for msg in state["messages"] if isinstance(msg, AIMessage)):
            state["messages"].append(AIMessage(content=f"Statement 2: {problem_statement_2}"))
        else:
            # Replace the existing Statement 2 message
            for i, msg in enumerate(state["messages"]):
                if isinstance(msg, AIMessage) and msg.content.startswith("Statement 2:"):
                    state["messages"][i] = AIMessage(content=f"Statement 2: {problem_statement_2}")
                    break
        
        # Reset regeneration flag
        state["regenerate_problem_statement_2"] = False
        
        # Update instructions for the next user input (choosing between statements with regeneration option)
        state["input_instructions"] = {
            "choice": "Select 'statement 1', 'statement 2', or 'regenerate' to get a new alternative statement"
        }
        state["awaiting_choice"] = True
        state["current_step"] = "request_choice"
        
        return state

    except Exception as e:
        state["problem_statement_2"] = f"Error generating problem statement 2: {str(e)}"
        return state

def request_choice(state: IdeationState) -> IdeationState:
    """Request user to choose between the two problem statements or regenerate either statement."""
    # Simply prepare the state for user choice without calling the LLM
    state["awaiting_choice"] = True
    state["input_instructions"] = {
        "choice": "Select between 'statement 1', 'statement 2', 'r1' to regenerate statement 1, or 'r2' to regenerate statement 2",
        "options": {
            "statement 1": state["problem_statement"],
            "statement 2": state["problem_statement_2"],
            "r1": "Regenerate Statement 1",
            "r2": "Regenerate Statement 2"
        }
    }
    state["current_step"] = "await_choice"
    
    return state

def process_user_choice(state: IdeationState, choice: str) -> IdeationState:
    """Process user's choice between the two problem statements or request for regeneration."""
    # Normalize choice to handle different input formats
    normalized_choice = choice.lower().strip()
    
    # Check if the user wants to regenerate problem statements
    if "r1" in normalized_choice or "regenerate 1" in normalized_choice or "regenerate statement 1" in normalized_choice:
        state["regenerate_problem_statement_1"] = True
        # Save message about regeneration request
        state["messages"].append(HumanMessage(content="I'd like to regenerate the first problem statement."))
        state["current_step"] = "generate_problem_statement"
        return state
    
    if "r2" in normalized_choice or "regenerate 2" in normalized_choice or "regenerate statement 2" in normalized_choice:
        state["regenerate_problem_statement_2"] = True
        # Save message about regeneration request
        state["messages"].append(HumanMessage(content="I'd like to regenerate the alternative problem statement."))
        state["current_step"] = "generate_problem_statement_2"
        return state
    
    # Set the final problem statement based on user choice
    if "1" in normalized_choice or "statement 1" in normalized_choice:
        state["final_problem_statement"] = state["problem_statement"]
        choice_text = "statement 1"
    elif "2" in normalized_choice or "statement 2" in normalized_choice:
        state["final_problem_statement"] = state["problem_statement_2"]
        choice_text = "statement 2"
    else:
        # Default to statement 1 if choice is unclear
        state["final_problem_statement"] = state["problem_statement"]
        state["feedback"] = "Unclear choice. Defaulting to statement 1."
        choice_text = "statement 1"
    
    # Add user choice to messages
    state["messages"].append(HumanMessage(content=f"I choose {choice_text}."))
    state["awaiting_choice"] = False
    state["regenerate_problem_statement_1"] = False
    state["regenerate_problem_statement_2"] = False
    state["input_instructions"] = {}  # Clear input instructions
    
    # Move to presenting exploration options instead of confirming
    state["current_step"] = "present_exploration_options"
    
    return state

def present_exploration_options(state: IdeationState) -> IdeationState:
    """Present the three fixed exploration options to the user."""
    # Display confirmation of the selected problem statement
    state["messages"].append(AIMessage(content=f"We'll use the following problem statement for our ideation session: {state['final_problem_statement']}"))
    
    # Initialize the mindmap with the problem statement as the central node
    state["mindmap"] = {
        "id": "root",
        "name": state["final_problem_statement"],
        "children": []
    }
    
    # Define the three fixed exploration options
    threads = [
        ("Emotional Root Causes", "Explore the underlying emotional needs, fears, or motivations"),
        ("Unconventional Associations", "Connect the problem to unexpected domains, metaphors, or analogies"),
        ("Imaginary Customers' Feedback", "Imagine different feedback perspectives on potential solutions")
    ]
    
    # Initialize the threads structure
    state["threads"] = {}
    for i, (name, description) in enumerate(threads, 1):
        thread_id = f"thread_{i}"
        state["threads"][thread_id] = {
            "id": thread_id,
            "name": name,
            "description": description,
            "messages": [SystemMessage(content=SYSTEM_TEMPLATE)],  # Each thread has its own message history
            "branches": {}  # Initialize branches for this thread
        }
        
        # Add to mindmap
        state["mindmap"]["children"].append({
            "id": thread_id,
            "name": name,
            "description": description,
            "children": []
        })
    
    # Set up for thread choice
    state["awaiting_thread_choice"] = True
    state["input_instructions"] = {
        "thread_choice": "Choose an exploration approach:",
        "options": {
            "1": "Emotional Root Causes - " + threads[0][1],
            "2": "Unconventional Associations - " + threads[1][1],
            "3": "Imaginary Customers' Feedback - " + threads[2][1]
        }
    }
    state["current_step"] = "await_thread_choice"
    
    return state

def get_thread_options_display(state: IdeationState) -> list:
    """Get a formatted list of thread options for display.
    This can be used by any interface (CLI, web, etc.)."""
    options = []
    
    # Use the existing threads state
    for i in range(1, 4):  # We have 3 fixed threads
        thread_id = f"thread_{i}"
        if thread_id in state["threads"]:
            thread = state["threads"][thread_id]
            name = thread["name"]
            desc = thread["description"]
            status = ""
            
            # Add status indicators if a thread is active or has been explored
            if state["active_thread"] == thread_id:
                status += " (current)"
            
            if len(thread["messages"]) > 1:
                status += " (explored)"
                
            options.append({
                "index": i,
                "id": thread_id,
                "name": name,
                "description": desc,
                "status": status,
                "display": f"{i}. {name}: {desc}{status}"
            })
    
    return options

def process_thread_choice_multi(state: IdeationState, choice: str) -> IdeationState:
    """Process the user's choice of which exploration approach to use without ending the session."""
    # Reset switching flag
    state["switch_thread"] = False
    
    # Check for "stop" command
    if choice.lower().strip() == "stop":
        state["current_step"] = "end_session"
        state["feedback"] = "Ending the ideation session as requested."
        return state
    
    # Check if choice is a branch selection (starts with 'b')
    if choice.lower().strip().startswith('b'):
        return process_branch_selection(state, choice)
    
    # Normalize and validate choice
    try:
        thread_num = int(choice.strip())
        if thread_num < 1 or thread_num > 3:
            raise ValueError("Thread choice must be 1, 2, or 3")
    except ValueError:
        # Try to match by name
        thread_map = {
            "emotional": "1",
            "emotional root": "1",
            "emotional root causes": "1",
            "root causes": "1",
            "unconventional": "2",
            "unconventional associations": "2",
            "associations": "2",
            "imaginary": "3",
            "feedback": "3",
            "imaginary customers": "3",
            "customers feedback": "3",
            "imaginary customers' feedback": "3"
        }
        normalized_choice = choice.lower().strip()
        thread_choice = thread_map.get(normalized_choice)
        if thread_choice:
            thread_num = int(thread_choice)
        else:
            state["feedback"] = "Invalid choice. Please select 1 (Emotional Root Causes), 2 (Unconventional Associations), or 3 (Imaginary Customers' Feedback), or select a branch by its index (b1, b2, etc.)."
            state["switch_thread"] = True  # Return to thread selection
            return state
    
    # Set the active thread
    thread_id = f"thread_{thread_num}"

    # Check if user is re-selecting a thread they've already explored
    is_reselection = (thread_id == state["active_thread"] and 
                       len(state["threads"][thread_id]["messages"]) > 1)
    
    # If re-selecting, reset the thread's branches and clear exploration data
    if is_reselection:
        # Keep track of branches to remove from global registry
        branches_to_remove = []
        for branch_id, branch in state["branches"].items():
            if branch["thread_id"] == thread_id:
                branches_to_remove.append(branch_id)
        
        # Remove branches from global registry
        for branch_id in branches_to_remove:
            del state["branches"][branch_id]
        
        # Reset thread's branches and exploration data
        state["threads"][thread_id]["branches"] = {}
        if "exploration_data" in state["threads"][thread_id]:
            del state["threads"][thread_id]["exploration_data"]
        
        # Reset mindmap children for this thread
        thread_node = next((node for node in state["mindmap"]["children"] if node["id"] == thread_id), None)
        if thread_node:
            thread_node["children"] = []
            if "exploration_data" in thread_node:
                del thread_node["exploration_data"]
        
        # Add a message indicating regeneration
        state["messages"].append(HumanMessage(
            content=f"I'd like to regenerate ideas for the {state['threads'][thread_id]['name']} approach."
        ))
        
        # Add a new message to start the exploration from scratch
        thread_message = HumanMessage(
            content=f"Let's explore the problem statement through the lens of {state['threads'][thread_id]['name']} again."
        )
        state["threads"][thread_id]["messages"].append(thread_message)
    
    state["active_thread"] = thread_id
    state["active_branch"] = None  # Reset active branch when switching threads
    
    # Only add messages if this is the first time selecting this thread
    if len(state["threads"][thread_id]["messages"]) <= 1:  # Only has system message
        # Add user choice to main messages
        state["messages"].append(HumanMessage(content=f"I choose to explore {state['threads'][thread_id]['name']}."))
        
        # Add the choice to thread-specific messages
        thread_message = HumanMessage(content=f"Let's explore the problem statement through the lens of {state['threads'][thread_id]['name']}.")
        state["threads"][thread_id]["messages"].append(thread_message)
        
        # For now, just acknowledge the selection in a simplified workflow
        thread_name = state["threads"][thread_id]["name"]
        state["messages"].append(AIMessage(content=f"Great! We'll explore '{state['final_problem_statement']}' through the {thread_name} approach. This thread now has its own separate conversation history."))
    
    # In the future, this would set up for branch generation
    state["current_step"] = "thread_exploration"  # Mark that we're in thread exploration mode
    
    return state

def thread_exploration(state: IdeationState) -> IdeationState:
    """Handle exploration within a specific thread using the appropriate prompt template."""
    thread_id = state["active_thread"]
    if not thread_id:
        state["feedback"] = "No active thread selected."
        return state
    
    thread_name = state["threads"][thread_id]["name"]
    
    # Select the appropriate prompt template based on the thread
    prompt_template = None
    if thread_id == "thread_1":  # Emotional Root Causes
        prompt_template = EMOTIONAL_ROOT_CAUSES_PROMPT
    elif thread_id == "thread_2":  # Unconventional Associations
        prompt_template = UNCONVENTIONAL_ASSOCIATIONS_PROMPT
    elif thread_id == "thread_3":  # Imaginary Customers' Feedback
        prompt_template = IMAGINARY_FEEDBACK_PROMPT
    else:
        state["feedback"] = f"Unknown thread type: {thread_name}"
        return state
    
    try:
        # Get the messages from the thread
        thread_messages = state["threads"][thread_id]["messages"]
        
        # Format the prompt with the problem statement and thread-specific messages
        prompt = prompt_template.format_messages(
            problem_statement=state["final_problem_statement"],
            thread_messages=thread_messages
        )
        
        # Invoke the LLM
        response = llm.invoke(prompt)
        response_content = response.content.strip()
        
        # Add the LLM response to the thread messages
        state["threads"][thread_id]["messages"].append(AIMessage(content=response_content))
        
        # Add a notification to the main message history
        notification = f"Explored '{state['final_problem_statement']}' through the {thread_name} approach."
        state["messages"].append(AIMessage(content=notification))
        
        # Try to parse JSON from the response
        try:
            # First try to parse the whole response as JSON
            try:
                json_data = json.loads(response_content)
            except json.JSONDecodeError:
                # If that fails, try to extract JSON using regex
                json_pattern = re.search(r'(\{.*\}|\[.*\])', response_content, re.DOTALL)
                if json_pattern:
                    potential_json = json_pattern.group(0)
                    json_data = json.loads(potential_json)
                else:
                    raise Exception("No valid JSON found in the response")
            
            # Store the parsed JSON in the thread
            state["threads"][thread_id]["exploration_data"] = json_data
            
            # Find the thread node in the mindmap and add the data
            thread_node = next((node for node in state["mindmap"]["children"] if node["id"] == thread_id), None)
            if thread_node:
                thread_node["exploration_data"] = json_data
            
            # Create branches for this thread based on the exploration data
            create_branches_from_exploration(state, thread_id, json_data)
            
            state["feedback"] = f"Successfully explored the {thread_name} approach and captured structured data."
            
        except Exception as json_error:
            # JSON parsing failed, but the response is still saved
            print(f"Note: Could not parse JSON from response: {str(json_error)}")
            state["feedback"] = f"Explored the {thread_name} approach, but couldn't extract structured data."
        
        return state
        
    except Exception as e:
        # Handle any other errors that might occur
        import traceback
        print(traceback.format_exc())
        state["feedback"] = f"Error during {thread_name} exploration: {str(e)}"
        return state

def create_branches_from_exploration(state: IdeationState, thread_id: str, json_data: dict) -> None:
    """Create branches from the exploration data."""
    # Get access to the thread and its branches
    thread = state["threads"][thread_id]
    thread_name = thread["name"]
    
    # Process based on thread type
    branches = []
    
    if thread_id == "thread_1":  # Emotional Root Causes
        # Extract emotional seeds
        if "emotionalSeeds" in json_data:
            for idx, item in enumerate(json_data["emotionalSeeds"]):
                branches.append({
                    "heading": item["heading"],
                    "content": f"{item['explanation']} Product direction: {item['productDirection']}",
                    "source": "emotionalSeeds",
                    "source_idx": idx
                })
                
        # Extract habit & heuristic alignment
        if "habitHeuristicAlignment" in json_data:
            for idx, item in enumerate(json_data["habitHeuristicAlignment"]):
                branches.append({
                    "heading": item["heading"],
                    "content": f"{item['explanation']} Product direction: {item['productDirection']}",
                    "source": "habitHeuristicAlignment",
                    "source_idx": idx
                })
                
        # Extract delightful subversion
        if "delightfulSubversion" in json_data:
            for idx, item in enumerate(json_data["delightfulSubversion"]):
                branches.append({
                    "heading": item["heading"],
                    "content": f"{item['explanation']} Product direction: {item['productDirection']}",
                    "source": "delightfulSubversion",
                    "source_idx": idx
                })
    
    elif thread_id == "thread_2":  # Unconventional Associations
        # Extract attribute-based bridging
        if "attributeBasedBridging" in json_data:
            for idx, item in enumerate(json_data["attributeBasedBridging"]):
                branches.append({
                    "heading": item["heading"],
                    "content": f"{item['explanation']} Product direction: {item['productDirection']}",
                    "source": "attributeBasedBridging",
                    "source_idx": idx
                })
                
        # Extract broader domains
        if "broaderDomains" in json_data:
            for idx, item in enumerate(json_data["broaderDomains"]):
                branches.append({
                    "heading": item["heading"],
                    "content": f"{item['explanation']} Product direction: {item['productDirection']}",
                    "source": "broaderDomains",
                    "source_idx": idx
                })
                
        # Extract metaphorical links
        if "metaphoricalLinks" in json_data:
            for idx, item in enumerate(json_data["metaphoricalLinks"]):
                branches.append({
                    "heading": item["heading"],
                    "content": f"{item['explanation']} Product direction: {item['productDirection']}",
                    "source": "metaphoricalLinks",
                    "source_idx": idx
                })
    
    elif thread_id == "thread_3":  # Imaginary Customers' Feedback
        # Handle the array format for this thread
        if isinstance(json_data, list):
            for user_idx, user_item in enumerate(json_data):
                heading = user_item.get("heading", f"User {user_idx+1}")
                user_profile = user_item.get("userProfile", "")
                
                for feedback_idx, feedback_item in enumerate(user_item.get("feedback", [])):
                    branches.append({
                        "heading": heading,
                        "content": f"User: {user_profile}\nFeedback: {feedback_item.get('explanation', '')}\nProduct direction: {feedback_item.get('productDirection', '')}",
                        "source": "imaginaryFeedback",
                        "source_idx": user_idx,
                        "feedback_idx": feedback_idx
                    })
    
    # Add branches to the state with unique IDs
    for branch_data in branches:
        branch_id = f"b{state['branch_counter'] + 1}"
        state['branch_counter'] += 1
        
        # Create the branch
        new_branch = {
            "id": branch_id,
            "thread_id": thread_id,
            "heading": branch_data["heading"],
            "content": branch_data["content"],
            "source": branch_data.get("source", ""),
            "parent_branch": None,  # Top-level branches have no parent
            "children": [],  # Initialize empty children list
            "expanded": False,  # Track if this branch has been expanded
            "expansion_data": None  # Will store expansion data when expanded
        }
        
        # Add to global branches registry and thread-specific branches
        state["branches"][branch_id] = new_branch
        thread["branches"][branch_id] = new_branch
        
        # Add to mindmap
        thread_node = next((node for node in state["mindmap"]["children"] if node["id"] == thread_id), None)
        if thread_node:
            # Add branch to thread node's children
            branch_node = {
                "id": branch_id,
                "name": branch_data["heading"],
                "content": branch_data["content"],
                "children": []  # Initialize empty children for future expansions
            }
            thread_node["children"].append(branch_node)


def generate_default_guidance(state: IdeationState, branch_id: str) -> str:
    """Generate contextually relevant default guidance for concept expansion."""
    branch = state["branches"][branch_id]
    
    try:
        # Create prompt for generating default guidance
        prompt = DEFAULT_GUIDANCE_PROMPT.format_messages(
            problem_statement=state["final_problem_statement"],
            concept_to_expand=f"{branch['heading']}: {branch['content']}",
            context=f"From {state['threads'][branch['thread_id']]['name']} exploration."
        )
        
        # Invoke the LLM
        response = llm.invoke(prompt)
        default_guidance = response.content.strip()
        
        # Clean up the response if needed (remove quotes, etc.)
        if default_guidance.startswith('"') and default_guidance.endswith('"'):
            default_guidance = default_guidance[1:-1]
        
        return default_guidance
        
    except Exception as e:
        # Fallback to static default if generation fails
        print(f"Error generating default guidance: {str(e)}")
        return DEFAULT_GUIDANCE_PROMPT


def display_available_branches(state: IdeationState) -> None:
    """Format and display available branches for selection."""
    # Check if there are any branches
    if not state["branches"]:
        print("No branches available yet. Please explore a thread first.")
        return
    
    print("\n===== AVAILABLE BRANCHES =====")

    # Create a set to track branches that have been displayed
    displayed_branches = set()

    # Group branches by thread
    for thread_id, thread in state["threads"].items():
        thread_name = thread["name"]
        
        # Find top-level branches for this thread (those with no parent)
        top_level_branches = [b for b_id, b in state["branches"].items() 
                             if b["thread_id"] == thread_id and b["parent_branch"] is None]
        
        if top_level_branches:
            print(f"\n{thread_name}:")
            
            # Display each top-level branch and its children
            for branch in top_level_branches:
                branch_id = branch["id"]
                expanded_marker = " [expanded]" if branch["expanded"] else ""
                current_marker = " *" if state["active_branch"] == branch_id else ""
                
                print(f"  {branch_id}{current_marker}: {branch['heading']}{expanded_marker}")
                # Print content in a formatted way
                content_lines = branch['content'].split('\n')
                for line in content_lines:
                    print(f"      {line}")
                print()  # Empty line for better readability
                
                # Track this branch as displayed
                displayed_branches.add(branch_id)
                
                # Display children branches if any
                if branch["children"]:
                    display_child_branches(state, branch, displayed_branches, indent=4)
    
    print("\n=============================")

def display_child_branches(state: IdeationState, parent_branch: dict, displayed_branches: set, indent: int = 4):
    """Helper function to display child branches recursively."""
    for child_id in parent_branch["children"]:
        # Skip if already displayed
        if child_id in displayed_branches:
            continue
            
        child = state["branches"].get(child_id)
        if child:
            expanded_marker = " [expanded]" if child["expanded"] else ""
            current_marker = " *" if state["active_branch"] == child_id else ""
            
            # Display the child branch with proper indentation
            indent_spaces = " " * indent
            print(f"{indent_spaces}{child_id}{current_marker}: {child['heading']}{expanded_marker}")
            
            # Print content in a formatted way
            content_lines = child['content'].split('\n')
            for line in content_lines:
                print(f"{indent_spaces}    {line}")
            print()  # Empty line for better readability
            
            # Track this branch as displayed
            displayed_branches.add(child_id)
            
            # Recursively display this branch's children
            if child["children"]:
                display_child_branches(state, child, displayed_branches, indent + 4)

def process_branch_selection(state: IdeationState, choice: str) -> IdeationState:
    """Process user's selection of a branch."""
    # Extract branch ID from choice (e.g., "b1", "b23")
    branch_match = re.match(r'b(\d+)', choice.lower().strip())
    if not branch_match:
        state["feedback"] = "Invalid branch selection format. Use 'b' followed by the branch number (e.g., b1, b2)."
        return state
    
    branch_num = branch_match.group(1)
    branch_id = f"b{branch_num}"
    
    # Check if branch exists
    if branch_id not in state["branches"]:
        state["feedback"] = f"Branch {branch_id} does not exist."
        return state
    
    # Set the active branch
    state["active_branch"] = branch_id
    branch = state["branches"][branch_id]
    
    # Set the active thread to the branch's thread
    state["active_thread"] = branch["thread_id"]
    
    # Add message about branch selection
    state["messages"].append(HumanMessage(content=f"I want to explore branch {branch_id}: {branch['heading']}"))
    
    # If the branch has already been expanded, show the expansion
    if branch["expanded"] and branch["expansion_data"]:
        # Create a response from the existing expansion data
        expansion_data = branch["expansion_data"]
        
        # Format a response showing the expansion
        response = f"Here's the existing expansion for {branch_id}: {branch['heading']}\n\n"
        response += f"Analysis: {expansion_data.get('analysis', '')}\n\n"
        
        # Add applications
        response += "Applications:\n"
        for app in expansion_data.get("applications", []):
            response += f"- {app.get('heading', '')}: {app.get('explanation', '')}\n"
        
        response += "\nWould you like to expand on a specific aspect or create a new expansion?"
        
        state["messages"].append(AIMessage(content=response))
        state["current_step"] = "branch_expansion_options"
    else:
        # Set up for concept expansion input
        state["awaiting_concept_input"] = True
        state["concept_expansion_context"] = {
            "branch_id": branch_id,
            "heading": branch["heading"],
            "content": branch["content"]
        }

        # Generate suggested guidance
        suggested_guidance = generate_default_guidance(state, branch_id)
        state["concept_expansion_context"]["suggested_guidance"] = suggested_guidance
        
        # Update input instructions
        state["input_instructions"] = {
            "concept_guidance": f"How would you like to expand branch {branch_id}: {branch['heading']}?\n(Enter your guidance or press Enter to use the suggestion below)\n\nSuggested guidance: {suggested_guidance}"
        }
        
        state["current_step"] = "await_concept_input"
        state["messages"].append(AIMessage(content=f"Selected branch {branch_id}: {branch['heading']}. Please provide any specific guidance for expanding this concept, or press Enter to use default guidance."))
    
    return state

def process_concept_input(state: IdeationState, user_input: str) -> IdeationState:
    """Process user input for concept expansion."""
    # Get branch information
    branch_id = state["concept_expansion_context"]["branch_id"]
    branch = state["branches"][branch_id]
    
    # Use the suggested guidance if no input provided
    if not user_input.strip():
        concept_guidance = state["concept_expansion_context"]["suggested_guidance"]
        print(f"Using suggested guidance: {concept_guidance}")
        user_message = f"I'll use the suggested guidance: {concept_guidance}"
    else:
        concept_guidance = user_input.strip()
        user_message = concept_guidance
    
    # Update the context with the guidance
    state["concept_expansion_context"]["guidance"] = concept_guidance
    state["messages"].append(HumanMessage(content=concept_guidance if user_input.strip() else "Please proceed with default guidance."))
    
    # Reset awaiting flag
    state["awaiting_concept_input"] = False
    
    # Move to concept expansion
    state["current_step"] = "expand_concept"
    
    return state

def expand_concept(state: IdeationState) -> IdeationState:
    """Expand a concept based on user guidance."""
    # Get concept information from context
    context = state["concept_expansion_context"]
    branch_id = context["branch_id"]
    branch = state["branches"][branch_id]
    
    try:
        # Create prompt for concept expansion
        prompt = CONCEPT_EXPANSION_PROMPT.format_messages(
            concept_to_expand=f"{branch['heading']}: {branch['content']}",
            context=f"From {state['threads'][branch['thread_id']]['name']} perspective",
            problem_statement=state["final_problem_statement"],
            user_guidance=context["guidance"]
        )
        
        # Invoke the LLM
        response = llm.invoke(prompt)
        response_content = response.content.strip()
        
        # DEBUG: Print the raw LLM response
        # print("\n===== DEBUG: RAW LLM RESPONSE =====")
        # print(response_content)
        # print("===== END RAW RESPONSE =====\n")

        # Strip markdown code block formatting if present
        response_content = strip_markdown_code_blocks(response_content)

        # Try to parse JSON from the response
        try:
            # Parse the JSON
            json_data = json.loads(response_content)
            
            # Normalize the JSON structure
            expanded_concepts = []
            
            # If JSON is an array, use it directly as expanded concepts
            if isinstance(json_data, list):
                expanded_concepts = json_data
                # Also store in a structured format for consistency
                json_data = {"expandedConcepts": expanded_concepts}
                print("Converted JSON array to object with expandedConcepts field")
            # If JSON is a dictionary, look for expandedConcepts field
            elif isinstance(json_data, dict):
                expanded_concepts = json_data.get("expandedConcepts", [])
            
            # Mark the branch as expanded and store expansion data
            branch["expanded"] = True
            branch["expansion_data"] = json_data
            
            # Create sub-branches from the expanded concepts
            for idx, concept in enumerate(expanded_concepts):
                # Create a new branch for each expanded concept
                sub_branch_id = f"b{state['branch_counter'] + 1}"
                state['branch_counter'] += 1
                
                # Create the sub-branch
                sub_branch = {
                    "id": sub_branch_id,
                    "thread_id": branch["thread_id"],
                    "heading": concept.get("heading", f"Concept {idx+1}"),
                    "content": f"{concept.get('explanation', '')} Product Direction: {concept.get('productDirection', '')}",
                    "source": "concept_expansion",
                    "parent_branch": branch_id,
                    "children": [],
                    "expanded": False,
                    "expansion_data": None
                }
                
                # Add to global branches registry
                state["branches"][sub_branch_id] = sub_branch
                
                # Add to parent branch's children list
                branch["children"].append(sub_branch_id)
                
                # Add to mindmap
                thread_node = next((node for node in state["mindmap"]["children"] if node["id"] == branch["thread_id"]), None)
                if thread_node:
                    branch_node = next((node for node in thread_node["children"] if node["id"] == branch_id), None)
                    if branch_node:
                        # Add sub-branch to branch node's children
                        sub_branch_node = {
                            "id": sub_branch_id,
                            "name": sub_branch["heading"],
                            "content": sub_branch["content"],
                            "children": []
                        }
                        branch_node["children"].append(sub_branch_node)
            
            # Format a user-friendly response showing expansion results
            result_message = format_expansion_results(json_data, branch_id, branch["heading"], expanded_concepts)
            state["messages"].append(AIMessage(content=result_message))
            
            state["feedback"] = f"Successfully expanded concept '{branch['heading']}' and created {len(expanded_concepts)} sub-branches."
            
        except Exception as json_error:
            # JSON parsing failed
            print(f"Note: Could not parse JSON from expansion response: {str(json_error)}")
            
            # Store the raw response as expansion data
            branch["expanded"] = True
            branch["expansion_data"] = {"raw_response": response_content}
            
            # Add raw response to messages
            state["messages"].append(AIMessage(content=f"Expanded concept '{branch['heading']}':\n\n{response_content}"))
            
            state["feedback"] = f"Expanded concept '{branch['heading']}', but couldn't extract structured data."
            
        # Return to thread/branch selection
        state["current_step"] = "present_exploration_options"
        state["concept_expansion_context"] = {}  # Clear context
        
        return state
        
    except Exception as e:
        # Handle any other errors
        import traceback
        print(traceback.format_exc())
        state["feedback"] = f"Error during concept expansion: {str(e)}"
        state["current_step"] = "present_exploration_options"
        return state
        
def strip_markdown_code_blocks(content: str) -> str:
    """Strip markdown code block formatting from the content."""
    # Remove ```json and ``` markers
    if content.startswith("```") and content.endswith("```"):
        # Find the first newline to skip the language identifier line
        first_newline = content.find('\n')
        if first_newline != -1:
            # Extract content between first newline and last ```
            content = content[first_newline:].strip()
            # Remove the trailing ```
            if content.endswith("```"):
                content = content[:-3].strip()
    
    # If it starts with ```json but doesn't properly end with ```, just remove the start
    elif content.startswith("```json") or content.startswith("```"):
        # Find the first newline to skip the language identifier line
        first_newline = content.find('\n')
        if first_newline != -1:
            content = content[first_newline:].strip()
    
    return content

def format_expansion_results(json_data: dict, branch_id: str, branch_heading: str, expanded_concepts=None) -> str:
    """Format expansion results in a user-friendly way."""
    result = f"## Expanded Concept: {branch_heading} ({branch_id})\n\n"
    
    # Add expanded concepts
    expanded_concepts = json_data.get("expandedConcepts", [])
    if expanded_concepts:
        result += "### Expanded Concepts\n"
        for idx, concept in enumerate(expanded_concepts, 1):
            result += f"{idx}. **{concept.get('heading', '')}**\n"
            result += f"   Explanation: {concept.get('explanation', '')}\n"
            result += f"   Product Direction: {concept.get('productDirection', '')}\n\n"
    
    # Add note about sub-branches
    result += f"\nSub-branches have been created for each expanded concept. You can select them using their branch IDs."
    
    return result

def end_session(state: IdeationState) -> IdeationState:
    """End the ideation session."""
    # Simply set the current step to indicate the session has ended
    state["current_step"] = "session_ended"
    state["feedback"] = "Ideation session ended."
    
    return state

def run_cli_workflow():
    """Run the ideation workflow as a CLI application."""
    print("\n===== IDEATION WORKFLOW CLI =====\n")
    print("Starting a new ideation session...\n")
    
    # Initialize state
    state = {
        "messages": [SystemMessage(content=SYSTEM_TEMPLATE)],
        "feedback": "",
        "context": {},
        "problem_statement": "",
        "problem_statement_2": "",  # Renamed from refined_problem_statement
        "final_problem_statement": "",
        "waiting_for_input": False,
        "awaiting_choice": False,
        "input_instructions": {},
        "regenerate_problem_statement_1": False,
        "regenerate_problem_statement_2": False,
        # New fields for exploration options
        "threads": {},
        "active_thread": None,
        "awaiting_thread_choice": False,
        "switch_thread": False,  # Flag for switching between threads
        "mindmap": {},
        "current_step": "initial_input",
        # New fields for branch management
        "branches": {},
        "branch_counter": 0,
        "active_branch": None,
        "awaiting_branch_choice": False,
        "awaiting_concept_input": False,
        "concept_expansion_context": {}
    }
    
    # Step 1: Request input (get instructions on what to collect)
    state = request_input(state)
    
    # Use the instructions from the state to prompt the user
    for field, prompt in state["input_instructions"].items():
        print(f"{prompt} ")
        user_input = input()
        state["context"][field] = user_input
    
    # Add user inputs to messages
    state["messages"].append(HumanMessage(content=f"Target audience: {state['context']['target_audience']}\nProblem: {state['context']['problem']}"))
    state["waiting_for_input"] = False
    
    # Step 2: Generate problem statement 1
    print("\nGenerating problem statement 1...")
    state = generate_problem_statement(state)
    print(f"Statement 1: {state['problem_statement']}\n")
    
    # Loop until user selects a final problem statement
    final_statement_selected = False
    
    while not final_statement_selected:
        # Check if we need to regenerate statements
        if state["regenerate_problem_statement_1"]:
            print("Regenerating problem statement 1...")
            state = generate_problem_statement(state)
            print(f"Statement 1: {state['problem_statement']}\n")
            state["regenerate_problem_statement_1"] = False
        
        if not state["problem_statement_2"] or state["regenerate_problem_statement_2"]:
            print("Generating problem statement 2...")
            state = generate_problem_statement_2(state)
            print(f"Statement 2: {state['problem_statement_2']}\n")
            state["regenerate_problem_statement_2"] = False
        
        # Display choices to user
        print("Please choose which problem statement to use:")
        print(f"1. Statement 1: {state['problem_statement']}")
        print(f"2. Statement 2: {state['problem_statement_2']}")
        print("r1. Regenerate Statement 1")
        print("r2. Regenerate Statement 2")
        
        choice = input("Enter '1', '2', 'r1', or 'r2': ").lower()
        
        # Process user choice
        state = process_user_choice(state, choice)
        
        # Check if we need to regenerate or proceed
        if state["regenerate_problem_statement_1"] or state["regenerate_problem_statement_2"]:
            continue
        else:
            final_statement_selected = True
    
    print(f"\nYou selected: {choice}")
    print(f"Final problem statement: {state['final_problem_statement']}\n")
    
    # Step 3: Present exploration options (instead of confirming problem statement)
    print("Now let's explore this problem from different angles.")
    state = present_exploration_options(state)

    # Display the thread options using the helper function
    print("\nExploration approaches:")
    thread_options = get_thread_options_display(state)
    for option in thread_options:
        print(option["display"])
    
    # Start multi-thread exploration using state graph workflow
    exploring = True
    
    while exploring:
        # Display available branches
        display_available_branches(state)
        
        # Show the exploration options
        print("\nChoose next action:")
        print("1-3: Select a thread (exploration approach)")
        print("b#: Select a branch (e.g., b1, b2, b3)")
        print("stop: End the ideation session")
        
        # Get user choice
        user_choice = input("\nEnter your choice: ").lower()
        
        # Check for stop command
        if user_choice.strip() == "stop":
            exploring = False
            state = end_session(state)
            continue
        
        # Set up context for processing
        state["context"]["thread_choice"] = user_choice
        
        # Process thread or branch choice
        if user_choice.startswith('b'):
            # Branch selection
            state = process_branch_selection(state, user_choice)
            
            # If awaiting concept input
            if state["awaiting_concept_input"]:
                # Get the suggested guidance from the context
                suggested_guidance = state["concept_expansion_context"]["suggested_guidance"]
                
                # Display the prompt with suggested guidance
                print(f"\nPlease provide guidance for expanding branch {state['concept_expansion_context']['branch_id']}: {state['concept_expansion_context']['heading']}")
                print(f"(Enter your guidance or press Enter to use this suggestion)")
                print(f"\nSuggested guidance: {suggested_guidance}")
                
                concept_input = input("\nYour guidance: ")
                
                # Process concept input
                state = process_concept_input(state, concept_input)
                
                # Expand the concept
                print(f"\nExpanding concept {state['concept_expansion_context']['branch_id']}...")
                state = expand_concept(state)
                
                # Display feedback
                if state["feedback"]:
                    print(f"\n{state['feedback']}")
                    state["feedback"] = ""
        else:
            # Thread selection or other action
            old_thread = state["active_thread"]
            old_step = state["current_step"]
            
            # Process thread choice
            state = process_thread_choice_multi(state, user_choice)
            
            # If stopping, break the loop
            if state["current_step"] == "end_session":
                exploring = False
                continue
                
            # If switching threads, continue the loop to show options again
            if state.get("switch_thread", False):
                if state["feedback"]:
                    print(f"\n{state['feedback']}")
                    state["feedback"] = ""
                continue
                
            # If we selected a thread to explore, simulate the thread exploration
            if state["current_step"] == "thread_exploration":
                thread_id = state["active_thread"]
                thread_name = state["threads"][thread_id]["name"]
                
                print(f"\nNow exploring: {thread_name}")
                print(f"This thread has its own separate conversation history.")
                
                # Simulate thread exploration
                state = thread_exploration(state)
                
                # Display feedback
                if state["feedback"]:
                    print(f"\n{state['feedback']}")
                    state["feedback"] = ""
    
    print("\n===== WORKFLOW COMPLETED =====\n")
    
    return state

# Create the workflow
workflow = StateGraph(IdeationState)

# Add nodes
workflow.add_node("request_input", request_input)
workflow.add_node("generate_problem_statement", generate_problem_statement)
workflow.add_node("generate_problem_statement_2", generate_problem_statement_2)
workflow.add_node("request_choice", request_choice)
workflow.add_node("present_exploration_options", present_exploration_options)
workflow.add_node("process_thread_choice", lambda state: process_thread_choice_multi(state, state["context"].get("thread_choice", "")))
workflow.add_node("thread_exploration", thread_exploration)
workflow.add_node("process_branch_selection", lambda state: process_branch_selection(state, state["context"].get("branch_choice", "")))
workflow.add_node("process_concept_input", lambda state: process_concept_input(state, state["context"].get("concept_input", "")))
workflow.add_node("expand_concept", expand_concept)
workflow.add_node("end_session", end_session)

# Add edges with conditional logic for regeneration
workflow.add_edge("request_input", "generate_problem_statement")
workflow.add_edge("generate_problem_statement", "generate_problem_statement_2")
workflow.add_edge("generate_problem_statement_2", "request_choice")

# Add conditional edges for problem statement workflow
workflow.add_conditional_edges(
    "request_choice",
    lambda state: {
        "generate_problem_statement": state["regenerate_problem_statement_1"],
        "generate_problem_statement_2": state["regenerate_problem_statement_2"],
        "present_exploration_options": not (state["regenerate_problem_statement_1"] or state["regenerate_problem_statement_2"])
    }
)

# Add conditional edges for exploration options workflow
workflow.add_edge("present_exploration_options", "process_thread_choice")

# Add conditional edges for thread exploration and switching
workflow.add_conditional_edges(
    "process_thread_choice",
    lambda state: {
        "present_exploration_options": state.get("switch_thread", False),  # Switch to another thread
        "thread_exploration": not state.get("switch_thread", False) and state["current_step"] == "thread_exploration",  # Explore the selected thread
        "process_branch_selection": not state.get("switch_thread", False) and state["current_step"] == "process_branch_selection",  # Process branch selection
        "end_session": state["current_step"] == "end_session"  # End the session
    }
)

# Add edge from thread exploration back to thread selection
workflow.add_edge("thread_exploration", "present_exploration_options")

# Add conditional edges for branch selection and concept expansion
workflow.add_conditional_edges(
    "process_branch_selection",
    lambda state: {
        "process_concept_input": state["awaiting_concept_input"],
        "present_exploration_options": not state["awaiting_concept_input"]
    }
)

# Add edges for concept expansion
workflow.add_edge("process_concept_input", "expand_concept")
workflow.add_edge("expand_concept", "present_exploration_options")

# Set entry point
workflow.set_entry_point("request_input")

# Compile the graph (only once)
app = workflow.compile()

# Example usage function
def start_ideation_session() -> IdeationState:
    """Start a new ideation session with a fresh state."""
    initial_state = {
        "messages": [],  # Start with empty message history
        "feedback": "",
        "context": {},
        "problem_statement": "",
        "problem_statement_2": "",
        "final_problem_statement": "",
        "waiting_for_input": False,
        "awaiting_choice": False,
        "input_instructions": {},
        "regenerate_problem_statement_1": False,
        "regenerate_problem_statement_2": False,
        # New fields for exploration options
        "threads": {},
        "active_thread": None,
        "awaiting_thread_choice": False,
        "mindmap": {},
        "current_step": "initial_input",
        # New fields for branch management
        "branches": {},
        "branch_counter": 0,
        "active_branch": None,
        "awaiting_branch_choice": False,
        "awaiting_concept_input": False,
        "concept_expansion_context": {},
        "switch_thread": False  # Flag for switching between threads
    }
    
    # Add the system message to start fresh
    initial_state["messages"].append(SystemMessage(content=SYSTEM_TEMPLATE))
    
    return app.invoke(initial_state)

# If this file is run directly, execute the CLI workflow
if __name__ == "__main__":
    run_cli_workflow()

