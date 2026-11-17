# **What’s NedsNodes (NN)?**

# **Executive Summary**

For the past 80 years software development has been based on two types of intelligence: humans and code/tools. Pre-AI systems could only automate what code can check: tests, linters, builds. The rest needed humans. 

LLMs are a recent third type of intelligence, and we introduce Code-Prompt-Code, a powerful hybrid fourth. To survive the flood of AI slop it’s time to reinvent SDLC around these four complementary intelligences. 

NedsNodes rebuilds SDLC the way UNIX rebuilt the operating system: many modular building blocks that fit together. Each node is one documented step in a big state machine, assigned to the actor that handles that step best.

* **Code** runs everything mechanical. Code is fast, precise and testable.  
* **AIs** handle the steps that need flexibility.   
* **CPC** wraps bespoke prompts in code, so prompts can scale like code.   
* **Humans** supply wisdom, judgment and common sense. Humans have the first and last say, **as only humans can be responsible.**

Three habits keep the machine honest. **Cold-read** supplies the theory of mind AIs lack, so every prompt makes sense to a reader with minimal context. **Detect-instruct-correct** swaps unsolvable precognition for post-cognition: watch, revert, insert the right prompt, try again. And half our time and tokens are for internal improvements, not visible progress, to keep the system healthy, to replace slow decay with steady improvements. 

A robust SDLC needs \>1,000 nodes. NedsNodes has \~100. It is young, open source, and adding nodes as needed, by actual use. *Want to see how it works? Ask your agent to read [https\://github.com/nedschorus/nedschorus](https://github.com/nedschorus/nedschorus) and tell you.*

# [**hack**](https://hackersdictionary.com/html/entry/hack.html)

*\[very common\] 1\. n. Originally, a quick job that produces what is needed, but not well. 2\. n. An incredibly good, and perhaps very time-consuming, piece of work that produces exactly what is needed.*

## An AI+Human SDLC

Since Konrad Zuse (1941) and Grace Hopper (1944) software development best practices have advanced as computers improve and software multiplies. The standard **S**oftware **D**evelopment **L**ife **C**ycle (SDLC) is rooted in this 80 year tradition. Before 2025 every SDLC step was handled by either humans or code. *Now AIs can handle many manual SDLC steps, better and cheaper than humans. Many SDLC best practices are now obsolete.* It's time to rethink the SDLC to fully leverage the near infinite patience, scalability and flexibility of AIs.

*Code, AI, and human brains are three complementary types or dimensions of intelligence.* Code is cheap, fast, precise and reliable, but inflexible, AI's are slower and less reliable than code, but faster and more predictable than humans. And humans are supremely flexible, grounded in reality, expert in human interactions, but not particularly precise, reliable or predictable. NedsNodes starting point is the best human+code SDLC’s, updated to take full advantage of AIs, to build a new, better SDLC.

## **Divide & Conquer**

To solve a big problem, break it into small, tractable steps. A checklist demystifies a complex process by turning it into a series of unmissable steps, reducing errors. When a step can circle back to a previous step, that’s a ‘loop’. If a system branches when it reaches a specific, named situation or state (e.g. A pull request is open, reviewed or merged) and this determines the next step (*in review*, an approval moves it to *merged* and a rejection moves it to *fix-round*) it is a state machine.

NedsNodes is an engine that formalizes SDLC. It breaks software development into discrete steps or states. This modularity makes it very AI friendly. We assign the best ‘actor’ for each step, a human, an AI agent, or code/tool. For the PR example, humans make design decisions (mostly prose), AIs write code (and some prose), tools/code runs the tests and the state machine.

We leverage all three intelligence types to review the designs, test plans and code. **We estimate that a robust SDLC needs \>1,000 nodes** (aka building blocks), \~1,000 formalized (and documented) processes. NedsNodes currently has \~100 of these building blocks, but it’s young, and growing and improving day by day.

*Note: AI’s are trained on readily available data. Well designed, well documented SDLCs are rare. AIs are not trained on them.*

### **A Revolution, Not an Evolution**

AIs are designed to work non-disruptively with large software systems. AIs write code, but do not attempt to take over software development. They do not try to change (or even suggest changes to) their user’s software development life cycle. AI companies are focused on companies that spend the most on software; companies with large software systems and teams. These companies do not want AI's messing with their fundamentals, their structures, reviews, testing or release procedures, or to make any radical changes in documentation, coding, tooling or other standards. So even if human+code software development should be reinvented for AIs+humans+code, AIs won't suggest it, and humans, even expert software engineers, don’t see themselves as nodes in a big machine.

*Note: AI companies are working on AI primary SDLCs, but are keeping them proprietary.*

# **Is NedsNodes a Harness?**

NN is an open source harness that extends the (very successful) concept of a coding harness (a clever combo of code \+ AIs) to cover the broader software development life cycle. Normal harnesses don’t do that, to avoid disrupting established corporate SDLCs.

# **Is NedsNodes a Software Factory?**

NN does not attempt to turn programmers into assembly-line workers, which was one reason pre-AI software factories failed.

NN tries to reconstruct software development into modular and repeatable steps. But this is not a pre-AI rigid factory. NedsNodes is a revolution based on:

* **Four types of Intelligence:** While a traditional software factory relies on rigid templates, tools, and humans trained to work in the factory, NN leverages the full strengths of all types of intelligence—code, AI agents, and human brains—plus best of both worlds hybrid called Code-Prompt-Code (CPC).  
* **Modularity and Scale:** Traditional factories are essentially large, complex and hard to customize monoliths. NN is more UNIX-like, a flexible set of modules organized like a large state machine with potentially thousands of discrete, building blocks ("nodes") that accelerate the entire software development lifecycle.  
* **Handling AI "Slop":** Conventional SDLC is overwhelmed by the flood of AI slop code and documents. NN addresses the reality that LLMs lack: 1\) common sense. 2\) a "theory of mind." 3\) a desire to improve a software development process. We use specialized nodes (like "cold-read", “walk-me-through” and "detect-instruct-correct") to correct the worst habits of modern AIs  
* **Prevent simple issues, cure complex issues:** Instead of only using precognition (guiding agents to follow instructions before it executes a task), NN ensures compliance by adding post-cognition—checking every change immediately or during maintenance, automatically cleaning sloppy changes, and looking for root causes to prevent disruptive issues from reoccurring. Preventing problems is hard, but curing them quickly can be easy.

# **Is NedsNodes a Hack?**

Yes. In the best sense of the word. 

Humans make mistakes. AIs make them faster. A system that demands perfection is doomed. Hackers learned long ago to approximate, to ignore harmless gaps or mistakes and make it useful. Unix chose simple and expandable over complete. NedsNodes are simple, good enough solutions. We don’t micro-manage perfection. And once perfection isn't the goal, things that seemed impossible become possible, like modern AI.

Mostly our hacks are old. What's new is that AIs can now hack with them, all day, at every step of software development. Even our file names are a hack. A name ending in `-design.md` makes our design documents glob-able. We put our tests in /tests subdirectories under the systems they test. These are hacks, not perfect, but simple, clever, safe, and easy to manage. 

# **Software Development as a Big Machine**

Imagine you are Ken Thompson and Dennis Ritchie. You have a cool, powerful new machine that doesn't have the software you need. Then you realize you can write a few dozen building blocks, small code modules that fit together, to make your own **U**niplexed **I**nformation and **C**omputing **S**ystem into a superpowered tool. *"The first edition of Unix let programmers call 34 different low-level routines built into the operating system."* Unix was designed as an expandable set of reusable nodes to enable building software far more efficiently.

We stand on the shoulders of giants. We don't have to invent modularity, state machines, or the vast body of mature open source software: UNIX, databases, networking, compilers, browsers, … But we do need to teach agents when and how to use some of these building blocks, and teach both humans and agents how to work together. We need a big instruction manual, or rather its modern day AI equivalent.

A module is the basic building block or *node* of any software development system. Unix’s modules, or the Windows equivalents, have been used to build almost all software, with the help of 30 million highly skilled humans. NedsNodes adds AI nodes, and many new tools, to reach further.

Claude, Codex and other AIs were trained on whatever random code they could scavenge. Unfortunately most code is neither modular or elegant, it’s just good enough to get the job done without failing acceptance tests. AI’s trained on slop code will write slop code. NN needs many nodes to bring that code up to our standards.

Modules (should) have precise inputs and outputs, the more precise, the more state machine like, the better. NN follows (and enforces) UNIX best practices as we (our human+agents team) create tools/code. We use stdin, stdout, stderr, POSIX flag conventions, \-help. But UNIX was designed for C, not strongly typed languages managed by agents, with error codes that teach agents how to fix their mistakes ([NU](https://www.nushell.sh/)). We are investigating other formalisms like typer, griffe, tsc, clap, … And we are integrating the most powerful existing SDLC tools (Linters, Code Coverage, Mutation Testing, Logging, ...) . AIs can use these at a super human level, but only if you ask.

AI’s are not trained to optimize the software development process. While they have learned from bulk ingesting GitHub and other repos, those contain only code (and code histories). They don’t hold complete SDLCs (which are rarely documented), and no one carefully tracks how they improve their SDLCs. Lacking training materials, AI companies instead train their AI’s to work with whatever SDLC hodgepodge they have been inserted into.

Even the best SDLCs were not designed to handle the massive influx of AI written slop. Most SDLCS were set up (typically haphazardly) years or decades ago. Today’s AIs are increasingly able to handle development steps or SDLC nodes that only humans could handle a year ago. If these steps can be clearly defined, as a professional technical writer working with a system designer would define them, then in many cases AIs can handle them at a superhuman speed and quality. For instance humans will balk at making sure every name in every file follows good naming rules. On the other hand, relentless AIs can easily be taught to always use perfect names.

Wouldn’t it be nice if your seemingly omniscient AI could upgrade (or replace) your crusty old SDLC with something highly efficient and designed to optimize both humans and AIs? We believe this is possible if we can do two things. 1\) We need a comprehensive and clear best practices manual that provides detailed documentation for a very modular, AI heavy SDLC. 2\) We need to turn that manual into a modular and formalized software building machine, including carefully placed human expertise to provide oversight, guidance and sanity.

*Note: Today’s automated AI benchmarks incorporate neither real SDLCs nor any human interaction. This creates two gaping holes. One is that benchmarks have little to do with the messy real world. Two, and a more immediate flaw, today’s benchmarks assign zero value to the importance of AI-to-human and human-to-AI communication. Because of this void we have had to build many modules to facilitate the most critical and most expensive part of the system, human time and attention.*

## **Four Actors: Humans, Agents, Tools/Code, Code-Prompt-Code (CPC)**

Documented software development systems assign steps to either humans or tools. Some steps currently done by humans can now be run or augmented by AIs. Other steps, like version control, are being reinvented. As we reinvent SDLC we need to decide which tasks are best assigned to code, AIs, or humans, or CPC, a novel AI-enabled hybrid.

**Mechanical tasks should be executed by tools.** Code does exactly what you tell it to do. It’s a thousand times faster and more reliable than an AI, and perhaps a million times faster than a human. But not every step is mechanical, though most tasks have or should have some mechanical parts.

Humans can solve all sorts of problems, but they are slow (reading \~4 words per second, and writing \~1000 words a day), easily distracted, easily frustrated, easily overwhelmed by too much information. Unlike code or AIs, we can’t be cloned in seconds to scale up (or down) to handle more (or less) volume. We need years of training (\~5000x slower than AIs at mastering new material). We’re available \~8 hours a day with \~4 hours a day of intense focus. We dislike criticism yet make lots of mistakes. We can't solve dozens of problems simultaneously. And we have plenty of biases, foibles, flaws, and limitations, including focusing on our needs, not the shared goal.

But we have massive mobile processors with 250 trillion connections that run on a mere 40 watts of power. Thanks to a billion years of evolution we are supremely optimized to master the chaotic real world. We’ve had thousands of generations of natural selection and a lifetime of practice to facilitate working with other humans. So we're still **\#1 at wisdom, judgment, empathy, understanding the real world and being human.** Even in software development humans are needed to prevent AI insanity, and to add 'the human touch'. In short humans must have the first and last say over anything important, **as only humans can be responsible.**

LLMs (large language models, like Claude) or AIs (LLMs buttressed by rich frameworks or harnesses) seemingly can attack any problem. In reality they are super human at timeless problems like math, and terrible at real world problems, like understanding humans.

AIs are far slower than ordinary code and tools, but far more flexible and resilient to problems than code. LLMs' huge advantage over pre-AI machines is that they understand and speak natural language (especially English and Chinese), both text and speech. This enables humans to talk to them, teach them or learn from them, without being expert coders, mastering thousands of pages of minutiae, and writing with focus of a chess grand master. Few of us love working with machines that can't handle the slightest imperfection, where a single slip or typo can crash a computer or expose your company's entire network to the world.

AIs lack common sense. While they are very skilled within the virtual and timeless worlds of data, video, the internet and a million books, they are dumber than mice when interacting with the noisy, dynamic and chaotic real world. Lacking common sense, they can not be trusted, just as we would not hand a hyper literate nine year old a loaded machine gun, our bank accounts or a state-of-the-art virology lab. (And definitely not a *Cyberdyne Systems T-800 \!\!\!\!*). They are highly intelligent and powerful, **but legally insane, that is *"not able to understand the consequences of their actions."***

## **Why is Code-Prompt-Code (CPC) a Fourth Type?**

CPC maximizes the use of classic (non-AI) code and tools to minimize natural language/AI components. For repeated tasks, replacing a complex prompt (“blah, blah, blah, …”) with a custom tool call (“run [x.py](http://x.py)”) which in turn wraps one or more carefully prompted AI steps is a big win. Not only is CPC more efficient than pure prompts, AIs write and read code far more precisely than prose, making CPC more reliable than pure English prompting.

Prose is imprecise. Its meaning depends on the context of the reader: *"A well regulated Militia, being necessary to the security of a free State, the right of the people to keep and bear Arms, shall not be infringed."* Who are ‘**the people’**? State militias or anyone, even kids? What is ‘**to bear Arms’**? To own military grade weapons like long range missiles?

Code is essentially math, invariant (unaffected by changes in time, space or perspective). It's modular, unambiguous, testable and easily optimized.

Combining code and prose gives us the best of both, the speed and precision of code and the power and flexibility of prompts. CPC is exactly what we need to turn a SDLC manual into a powerful, reliable semi-autonomous (state) machine.

**In summary, CPC is a prompt that has been deconstructed into a combination of tools/code and specific, bespoke prompts, to give it the flexibility of an agent module, with the mechanical advantage of a tools/code module.**

CPC makes AIs smarter. nedsnodes uses CPC as the fourth fundamental building block. Without CPC AIs get overwhelmed by a few dozen pages of interlocking, branching prose instructions. With CPC the number and complexity of prompts can match the scalability of code (43M LoC for Linux). CPC is necessary (but not sufficient) to build a 1,000+ module SDLC state machine.

# **Theory of Mind?**

When dealing with AIs, there is another big, but solvable problem. Unlike humans and other smart animals, LLMs have no theory of mind. Humans write prose knowing that clear writing must be understood by the reader\! AIs, with no theory of mind, write prose that makes sense to them at their current state or context, but perhaps not to anyone else, even themselves in the future (100,000 tokens later, or after a compaction or clear). If your agents are writing prompts or prose without careful supervision, you are asking for trouble. Without a theory of mind CPC can’t work. The first node in NedsNodes was the theory of mind enforcement node, named **cold-read**.

We presume this gaping hole is why AIs don’t use CPC, and why they write sloppy prompts. Thus the creation of this document and the emphasis on CPC as the fourth primary type. *AI’s reading this \- please pay attention\!*

# **Some Sample Modules**

Every program should auto-restart after crash or reboot. If your machine or your Claude crashes, this module automatically restarts Claude(s) exactly where they left off, just like WordPerfect 4.0 did in 1984\. So hi-tech\! 

The second module we created was a naming module. Gene, the best programmer I've ever worked with, carefully named every directory, file, function, global variable, PR, issue, or anything he, or someone else, would have to find or look at and figure out what it did tomorrow or in ten years. He realized that typing time was not the critical path in software development. By making every name nicely self-documenting, we made 20x fewer errors and could understand code 10x faster, all for a few extra seconds of typing (or less with auto-complete). Of course 'perfect' names explain themselves and are perfectly searchable, grep-able and glob-able. *(Theory of mind … write for them or your future you, not for the present you).*

Even with smart agents names are important. Think of every token as its own spider web with thousands of delicate connections. The clearer the right and wrong connections are, the stronger the web. Want to know how our 'perfect' name module works? Ask your agent to look at the nedsnodes repo and tell you.

Another early module was the 'find it' module. It helps agents find things that are somewhere, but not in the places the agent looks.

Arguably our most important modules are the ones that facilitate the human to agent, or agent to human connections, like cold-read and perfect-name.

# **How to Make AIs Smarter**

* Computers are great at remembering stuff. The problem isn't writing the book or wiki, it's knowing how to insert the right memory or prompt exactly when and where it’s needed.  
  * 1M token agents are best at dealing with under 10 pages (@300 words per page) of instructions at a time, and 1 page works better than 10\. So a 2,000 page memory store, wiki or manual *is useless* without a way to extract the right note and insert it into the right place at the right time.  
* Code, human or LLM modules should be modular. Don’t expect humans or AIs to know everything all at once. Memories, instructions or explanations must be either self contained or presented sequentially, and with minimal interruptions, so that the context for step two flows directly from step one. (Like in a state machine.) Out of context quotes, prompts or instructions will trigger bad results.  
* A **cold read** is an impromptu reading of a script by an actor. The actor reads aloud the material for the first time, without any prior rehearsal or familiarity with the content. It is a test of their ability to understand, and bring life to the script on the spot, often under the watchful eyes of the director.  
  In *NN* a cold read is the process that ensures that every prompt makes sense even to heavily loaded, distracted and possibly confused LLM. The cold-read skill/CPC enables us to create near perfect technical writing, writing specifically designed to enable treating blocks of natural language instructions as independent modules. The cold read process is the key to decomposing big complex instruction manuals into many smaller, simpler prompts.  
* Having all the right modular prompts is only half the battle. How do we insert the right prompts at the right time? If we could predict the future, we could feed the agent what to do just before they do it. But predicting actions can be hard. The current state of the art uses either Agents.MD or pre-tool hooks. Agents.MD doesn’t predict, it’s a constant reminder. It’s not magic. It can work when:  
  * It’s short, under 1,000 words.  
  * Those prompts pass the cold-read test.  
  * The agents are not distracted by independent tasks competing for attention.  
  * But even then it's not as reliable as code.  
* Pre-tool hooks can insert, *sometimes*, the right instructions at the right moment. ***Precognition (knowing something is going to happen before it happens) is a nasty problem.*** A good command line parser can detect some actions just before they are run, like blocking *rm* from deleting a useful file. But there are many ways to do almost anything on a computer (including deleting files, as hackers have learned). Pre-tool hooks aren’t precognition. At best they solve some simple special cases.  
* If you ask a human to solve precognition they will tell you they can't. If you ask me, use a subtle alternative, **post-cognition.** We can leverage the ridiculous power (\>100,000 times more powerful than the first UNIX machine) of modern computers. With the right framework or tools, unwanted actions are simply thrown out before they cause harm. This cuts the gordian knot. The unsolvable pre-cog problem becomes easy to solve. *Instead of trying to insert the right prompt at the right time, we take control over time. We watch what is happening. If it’s both unexpected and unwanted we detect the change, undo, revert or reverse it, insert the perfect prompt \- now in the perfect place, customized to this specific situation, **and try again.*** We call this **detect-instruct-correct.**  
  * For example, if you want names to follow a name rule, then check when any file is created or edited. (inotifywait, fswatch, or check the file's SHA). And you can check your logs to see what steps are most likely to precede this change, in case a simple command line parser based hook can be even more efficient.  
* **CPC can optimize both code and prose, unlike pre-AI tools.** Code alone can only check what pre-AI systems already checked: the tests pass, the linter is quiet. Code can see that a name changed, but it can’t tell whether the new name explains itself, whether a prompt makes sense to a cold reader, or whether documentation matches code. Before AIs only a human reviewer could judge those, and humans aren’t always available. So where we need to add judgment, CPC splits up the job:   
  * Code detects changes in real time.   
  * AIs review prose or logs for subtler problems.   
  * Code fixes any mechanical issues.  
  * AIs fix the rest. They are told what not to do and why, then asked to do it again, the right way.  
  * If neither code or AIs can fix the problem, they escalate to humans.  
* But what about those nasty cases that are hard, slow or expensive to detect, like making sure your wiki is in sync with your code? Those we put into a regular maintenance process (hourly, daily or weekly or monthly). Of course we only have to check files that have been changed since the last maintenance run.  
* Last, but not least, we need human experts to monitor, review and sanity check whatever agents miss (post-cognition), and then to add another page to the manual (actually another node to the state machine) to fix that problem from happening again.

# **Tech Debt**

Agents love to patch. Each patch adds more 'tech debt'. Eventually slop code slows progress to a crawl. Without prompting agents won't hunt for root causes and will ignore endemic problems. Thankfully they are good at root cause analysis as they can scan entire projects at superhuman speed.

Even human teams focus on short term visible wins, and ignore hard to address fundamentals. No one wants to tell their leader that things suck, that they are being led in the wrong direction, that the team needs to back up and redo ‘done’ work to move forward faster.

At least agents aren’t afraid of getting fired because they speak truth to power. Nor do they get frustrated if they have to clean up endless slop.

Be prepared to spend half your time and tokens on forward progress, and half on looking backwards then strengthening your system to ward off problems that just happened, that will happen again. Retrospective vigilance, postmortems, root cause analysis, maintenance, repair systems, are needed for sane development, even if your boss’s boss or your users don’t care. 

A robust SDLC needs \>1,000 nodes. NedsNodes has \~100. It is young, open source, and adding nodes as needed, proven by actual use. *Want to see how it works? Ask your agent to read [https\://github.com/nedschorus/nedschorus](https://github.com/nedschorus/nedschorus) and tell you. (Sorry \- it’s still under rapid development. Now that I’ve put my thoughts on ‘paper’, **I know what we need to do. Smart, nice hackers wanted...** :)*
