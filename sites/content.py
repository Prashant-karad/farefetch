"""Content of the three publisher websites (original sample explainers).

Each site is a separate static website (see build.py). Code Dojo and MoneyWise are already on Fairfetch;
StudyNest is the site a publisher connects live during the walkthrough.
"""

SITES = {
    "codedojo": {
        "name": "Code Dojo",
        "tagline": "Programming concepts, explained without the jargon.",
        "color": "#e4572e", "ink": "#1d1a19", "paper": "#fbf7f2", "font": "Space Grotesk",
        "publisher_id": "pub_code_dojo",
        "articles": [
            ("what-is-oop", "What is object-oriented programming (OOP)?", 400, "lic_read_24h", """
Object-oriented programming is a way of organising code around objects: small bundles that keep data and the functions that work on that data together. A bank account object, for example, holds a balance and offers deposit and withdraw methods, so no other part of the program changes the balance directly.

OOP rests on four ideas. Encapsulation hides an object's internal state behind methods, so rules like "the balance can never go negative" live in one place. Abstraction lets you use an object through a simple interface without knowing how it works inside. Inheritance lets a SavingsAccount reuse everything an Account does and add interest on top. Polymorphism lets different objects answer the same call in their own way, so a list of shapes can all respond to area() even though a circle and a square calculate it differently.

The practical benefit is change: when every rule about accounts lives inside the Account class, a new requirement means editing one class instead of hunting through the whole program. The common mistake is deep inheritance chains; most experienced developers prefer composition, building objects out of smaller objects, and keep inheritance shallow.
"""),
            ("oop-in-five-minutes", "OOP in five minutes", 150, "lic_read_24h", """
Object-oriented programming is a way of organising code around objects that keep data and the functions that work on that data together. A bank account object holds a balance and offers deposit and withdraw methods. OOP rests on four ideas: encapsulation, abstraction, inheritance and polymorphism. Keep inheritance shallow and prefer composition.
"""),
            ("sql-joins-explained", "SQL JOINs explained with one example", 350, "lic_read_24h", """
A JOIN combines rows from two tables using a column they share. Imagine a customers table and an orders table, where each order stores the customer_id of the person who placed it.

An INNER JOIN returns only the pairs that match: customers who have placed at least one order, each next to their orders. A LEFT JOIN keeps every customer from the left table and fills the order columns with NULL when a customer has never ordered, which is how you find inactive customers: LEFT JOIN, then filter WHERE orders.id IS NULL. A RIGHT JOIN is the same idea from the other side, and a FULL OUTER JOIN keeps unmatched rows from both tables.

Two mistakes cause most wrong results. The first is joining on the wrong column, which silently multiplies rows. The second is putting a filter on the right table in the WHERE clause after a LEFT JOIN, which quietly turns it back into an INNER JOIN; put that condition in the ON clause instead. When numbers look too large, count rows before and after the join to see whether it multiplied them.
"""),
            ("big-o-in-plain-words", "Big-O notation in plain words", 300, "lic_read_24h", """
Big-O describes how the work a piece of code does grows as its input grows. It ignores exact timings and asks one question: if the input doubles, what happens to the work?

O(1) means the work stays the same, like reading an item from a dictionary by its key. O(log n) grows very slowly, like binary search, which halves the remaining list at every step, so a million items need only about twenty steps. O(n) grows in step with the input, like scanning a list once. O(n log n) is the cost of good sorting algorithms. O(n squared) appears when you compare every item with every other item, usually as a loop inside a loop, and it becomes painful quickly: ten times more data means a hundred times more work.

In practice, the biggest wins come from spotting an accidental O(n squared), such as checking membership in a list inside a loop, and replacing the list with a set so each check becomes O(1).
"""),
            ("git-merge-vs-rebase", "Git merge vs rebase: which one should you use?", 250, "lic_read_24h", """
Both commands bring changes from one branch into another; they differ in the history they leave behind. A merge creates a new merge commit that ties the two branches together and keeps every original commit exactly as it happened. A rebase replays your commits on top of the other branch, producing a straight line of history as if you had started your work later.

Merging is safe for shared branches because it never rewrites commits that other people may already have. Rebasing gives a cleaner history and is ideal for tidying your own feature branch before you open a pull request. The golden rule: never rebase commits that you have already pushed to a branch other people use, because rewriting them breaks everyone else's copy.
"""),
        ],
    },
    "studynest": {
        "name": "StudyNest",
        "tagline": "Homework help that actually explains the why.",
        "color": "#2f7d5b", "ink": "#16251f", "paper": "#f4f8f4", "font": "Fraunces",
        "publisher_id": None,  # joins Fairfetch live, through the setup flow
        "articles": [
            ("how-photosynthesis-works", "How photosynthesis works, step by step", None, None, """
Photosynthesis is how plants turn light into food. In the leaves, a green pigment called chlorophyll absorbs mostly red and blue light. The plant uses that energy to split water molecules taken up by the roots, which releases oxygen as a by-product; that is where the oxygen we breathe comes from.

The process happens in two stages inside the chloroplasts. In the light-dependent reactions, light energy is captured and stored in two energy-carrier molecules, ATP and NADPH. In the Calvin cycle, which does not need light directly, the plant uses that stored energy to fix carbon dioxide from the air into a three-carbon sugar, which it later builds into glucose and starch.

The overall equation is six carbon dioxide plus six water, with light, gives one glucose and six oxygen. A useful way to remember it: plants take in carbon dioxide and water, and give out sugar and oxygen. Photosynthesis slows down when light, water or carbon dioxide runs short, or when it is too cold or too hot for the enzymes involved.
"""),
            ("solve-quadratic-equations", "Solving quadratic equations: three methods", None, None, """
A quadratic equation has the form a x squared plus b x plus c equals zero, and it can have two, one or no real solutions. There are three standard ways to solve it.

Factoring works when the expression splits neatly: x squared minus 5x plus 6 equals zero becomes (x minus 2)(x minus 3) equals zero, so x is 2 or 3. Look for two numbers that multiply to c and add to b.

Completing the square rewrites the equation as a perfect square plus a constant. It is the method behind the formula and is useful for finding the vertex of a parabola.

The quadratic formula always works: x equals negative b, plus or minus the square root of b squared minus 4ac, all divided by 2a. The part under the root, b squared minus 4ac, is called the discriminant. If it is positive there are two real solutions, if it is zero there is exactly one, and if it is negative there are no real solutions. Check your answers by substituting them back into the original equation.
"""),
            ("newtons-three-laws", "Newton's three laws of motion, with everyday examples", None, None, """
Newton's first law says an object keeps doing what it is doing, staying still or moving in a straight line at the same speed, unless a force acts on it. That is why passengers lurch forward when a bus brakes suddenly: their bodies keep moving.

The second law links force, mass and acceleration: force equals mass times acceleration. Pushing an empty shopping cart and a full one with the same force, the empty one speeds up much faster because it has less mass.

The third law says every action has an equal and opposite reaction. When you jump off a small boat onto a dock, you push the boat backwards as it pushes you forwards, which is why the boat drifts away.

Most physics problems at school level use the second law: draw every force acting on the object, add them up to find the net force, then divide by the mass to get the acceleration.
"""),
            ("strong-essay-introduction", "How to write a strong essay introduction", None, None, """
A good introduction does three jobs in a few sentences: it catches interest, gives context and states your argument. Start with a hook that is specific to your topic, such as a surprising fact or a sharp question, rather than a sweeping statement about all of history. Then give just enough background for the reader to follow your point.

End with a clear thesis statement: one sentence that says what you will argue and, ideally, why. A weak thesis describes a topic; a strong thesis takes a position someone could disagree with. Many writers draft the introduction last, once they know exactly what the essay argues, and then make sure every paragraph that follows supports that thesis.
"""),
        ],
    },
    "moneywise": {
        "name": "MoneyWise",
        "tagline": "Money basics in plain English.",
        "color": "#3446c9", "ink": "#151831", "paper": "#f5f6fc", "font": "DM Serif Display",
        "publisher_id": "pub_moneywise",
        "articles": [
            ("compound-interest-explained", "Compound interest explained with simple numbers", 300, "lic_read_24h", """
Compound interest means you earn interest on your interest. If you put 1,000 dollars into an account paying 7 percent a year, you have 1,070 dollars after the first year. In the second year you earn 7 percent on 1,070, not on 1,000, so the growth speeds up every year.

Left alone for ten years, that 1,000 dollars grows to about 1,967 dollars; after thirty years it reaches about 7,612 dollars, without adding anything. The rule of 72 gives a quick estimate: divide 72 by the interest rate to see roughly how many years it takes to double your money, so at 7 percent it doubles about every ten years.

The lesson is that time matters more than the amount you start with. The same maths works against you on credit card debt, where interest is often above 20 percent a year and a balance can double in under four years if you only make minimum payments.
"""),
            ("what-is-an-index-fund", "What is an index fund?", 250, "lic_read_24h", """
An index fund is a single investment that holds every company in a market index, such as the 500 large companies in the S&P 500. Instead of paying a manager to pick winners, you buy a small slice of the whole market.

Index funds are popular for three reasons. They are diversified, so one company failing has little effect. They are cheap, with yearly fees often below 0.1 percent compared with around 1 percent for many actively managed funds. And over long periods most active managers fail to beat the index after fees. The trade-off is that you get the market's return, never more, and you still lose money when the whole market falls.
"""),
            ("how-credit-scores-work", "How credit scores work", 250, "lic_read_24h", """
A credit score is a number lenders use to estimate how likely you are to repay a loan. The most common scores run from 300 to 850. The biggest factor is payment history: paying every bill on time matters more than anything else. The second is how much of your available credit you use; keeping card balances below about 30 percent of your limits helps.

The length of your credit history, the mix of credit types and how often you apply for new credit make up the rest. Checking your own score does not lower it, but many applications for new credit in a short time can.
"""),
            ("inflation-in-plain-words", "Inflation in plain words", 200, "lic_read_24h", """
Inflation is the rate at which prices rise over time, which means the same money buys less. If inflation is 3 percent, something that costs 100 dollars today costs about 103 dollars a year from now. Cash in a savings account that pays less than inflation is quietly losing buying power. Central banks usually aim for low, steady inflation of around 2 percent and raise interest rates when prices climb too fast.
"""),
        ],
    },
}
