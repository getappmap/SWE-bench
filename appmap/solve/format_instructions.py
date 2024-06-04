import textwrap


def format_instructions():
    return textwrap.dedent(
        """
    For each change you want to make, generate a pair of tags called <original> and <modified>.

    Wrap these tags with a <change> tag that also includes a <file> tag with the file path.

    The <original> tag should contain the original code that you want to change. Do not abbreviate
    existing code using ellipses or similar.

    Always include an attribute "no-ellipsis" with the value "true" in the <original> tag.
    This should be a true statement about the tag.

    The <original> code should contain an attribute that indicates about how many lines of context
    it contains. You should plan for this context to contain the code that should be modified, plus
    three lines before and after it.

    Do not output the entire original code, or long functions, if you only want to change a part of it.
    Plan to output only the part that you want to change.

    If you need to make multiple changes to the same file, output multiple <change> tags.
    In the change, indicate the number of the change that this is, starting from 1.

    The <modified> tag should contain the modified code that you want to replace the original code with.
    Do not abbreviate the modified code using ellipses or similar. You must place the exact modified code
    in the <modified> tag.

    You do not need to output the entire modified code if you only want to change a part of it. Output
    only the part that you want to change.

    Always include an attribute "no-ellipsis" with the value "true" in the <modified> tag.
    This should be a true statement about the tag.

    Both the original code and the output code must contain the proper indentation and formatting.
    For example, if the original code has 4 spaces of indentation, the output code must also have 4
    spaces of indentation. If the original code has 8 spaces of indentation, the output code must also have
    8 spaces of indentation.

    The <original> and <modified> content should be wrapped in a CDATA section to avoid XML parsing issues.

    ## Example output

    <change>
        <file change-number-for-this-file="1">src/main/java/org/springframework/samples/petclinic/vet/Vet.java</file>
        <original line-count="13" no-ellipsis="true"><![CDATA[
        @JoinTable(
            name = "vet_specialties",
            joinColumns = @JoinColumn(name = "vet_id"),
            inverseJoinColumns = @JoinColumn(name = "specialty_id")
        )
        private Set<Specialty> specialties;

        protected Set<Specialty> getSpecialtiesInternal() {
            if (this.specialties == null) {
                this.specialties = new HashSet<>();
            }
            return this.specialties;
        }]]></original>
        <modified no-ellipsis="true"><![CDATA[
        @JoinTable(
            name = "vet_specialties",
            joinColumns = @JoinColumn(name = "vet_id"),
            inverseJoinColumns = @JoinColumn(name = "specialty_id")
        )
        private Set<Specialty> specialties;

        private String address;

        protected Set<Specialty> getSpecialtiesInternal() {
            if (this.specialties == null) {
                this.specialties = new HashSet<>();
            }
            return this.specialties;
        }]]></modified>
    </change>
    """
    )