
from shared.clients.llm.LLMClientInterface import LLMClientInterface
from shared.helper.HelperConfig import HelperConfig
from dataclasses import dataclass, field
from services.rag_search.helper.CacheHelper import RagResponse
import json

@dataclass
class MergedRagResponseOption:
    correspondents: list[str] = field(default_factory=list)
    document_types: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)

@dataclass
class PromptClassification:
    correspondent: str | None = None
    document_type: str | None = None
    tags: list[str] = field(default_factory=list)

class LLMHelper:
    def __init__(self, llm_client: LLMClientInterface, config: HelperConfig):
        self._llm_client = llm_client
        self.config = config
        self.logging = config.get_logger()
        self._max_filter_values: int = int(
            self.config.get_number_val("LLM_MAX_FILTER_VALUES_PER_CATEGORY", default=50)
        )

    async def _classify_query(
        self,
        query: str,
        rag_data: list[RagResponse],
        chat_history: list[dict] | None,
    ) -> PromptClassification:
        """Use the LLM to extract metadata filters from a natural language query.

        Fetches and merges filter option candidates from all provided identities,
        applies a word-overlap pre-filter to reduce prompt size, then calls
        do_chat() with the enriched system prompt. Returns an empty
        PromptClassification on any error.

        Args:
            query: The raw user query string.
            rag_data: List of RagResponse objects containing data from RAG clients.
            chat_history: Optional prior conversation turns for context.

        Returns:
            PromptClassification with safely extracted fields; empty on any error.
        """        
        #Merge filter options and sort for deterministic prompt construction
        options = self.merge_rag_data(rag_data)

        # Apply word-overlap filter to avoid overwhelming the context window
        options = self.limit_rag_options(options, query)

        # Generate classification payload
        messages = self.create_classification_payload(options, query, chat_history)

        # do the call. If an error occures, let it throw
        raw_response = await self._llm_client.do_chat(messages)

        # Strip markdown code fences if present
        text = raw_response.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            lines = [ln for ln in lines if not ln.strip().startswith("```")]
            text = "\n".join(lines).strip()
    
        # parse to dict
        data = json.loads(text)
        if not isinstance(data, dict):
            raise ValueError(f"LLM response is not a dict object: {data}")
        
         # now validate the values returned by llm and create response
        return self.validate_classification(data, options)
    
    ##########################################
    ################ RAG DATA ################
    ##########################################

    def merge_rag_data(self, rag_data: list[RagResponse]) -> MergedRagResponseOption:
        """
        Merge data from multiple RagResponse objects into unified sets of correspondents, document types, and tags.

        Args:
            rag_data: List of RagResponse objects containing data from RAG clients.
        Returns:
            MergedRagResponseOption: An object containing merged lists of unique correspondents, document types, and tags.
        """
        # Merge filter options from all identities
        all_correspondents: set[str] = set()
        all_document_types: set[str] = set()
        all_tags: set[str] = set()
        for rd in rag_data:
            all_correspondents.update(rd.correspondents)
            all_document_types.update(rd.document_types)
            all_tags.update(rd.tags)
        
        #sort options for deterministic prompt construction
        return MergedRagResponseOption(
            correspondents=sorted(all_correspondents),
            document_types=sorted(all_document_types),
            tags=sorted(all_tags),
        )
    
    def limit_rag_options(self, options: MergedRagResponseOption, query: str) -> MergedRagResponseOption:
        """
        Apply word-overlap filtering and hard limits to merged RAG options to ensure prompt fits within LLM context window.

        Args:
            options: MergedRagResponseOption containing lists of correspondents, document types, and tags.
            query: The raw user query string, used for word-overlap filtering.
        Returns:
            MergedRagResponseOption with filtered and limited lists of correspondents, document types, and tags.
        """
        # Apply word-overlap filter to avoid overwhelming the context window
        correspondents = self._filter_by_word_overlap(query, options.correspondents)
        document_types = self._filter_by_word_overlap(query, options.document_types)
        tags = self._filter_by_word_overlap(query, options.tags)

        # Apply hard limits to ensure prompt fits within context window even in worst case. Log a warning if limits are hit, as this may degrade classification quality.
        if len(correspondents) > self._max_filter_values:
            self.logging.warning(f"Number of correspondents after filtering ({len(correspondents)}) exceeds max of {self._max_filter_values}. Truncating list, which may degrade classification quality.")
            correspondents = correspondents[: self._max_filter_values]
        if len(document_types) > self._max_filter_values:
            self.logging.warning(f"Number of document types after filtering ({len(document_types)}) exceeds max of {self._max_filter_values}. Truncating list, which may degrade classification quality.")
            document_types = document_types[: self._max_filter_values]
        if len(tags) > self._max_filter_values:
            self.logging.warning(f"Number of tags after filtering ({len(tags)}) exceeds max of {self._max_filter_values}. Truncating list, which may degrade classification quality.")
            tags = tags[: self._max_filter_values]

        return MergedRagResponseOption(
            correspondents=correspondents,
            document_types=document_types,
            tags=tags,
        )

    def _filter_by_word_overlap(self, query: str, values: list[str]) -> list[str]:
        """
        Keep only values that share at least one meaningful token with the query.

        Args:
            query: The raw user query string.
            values: List of candidate filter values to be matched against the query.

        Returns:
            List of values that share at least one token with the query.
        """
        query_tokens = {t for t in query.lower().split() if len(t) > 2}
        if not query_tokens:
            return []
        return [v for v in values if {t for t in v.lower().split()} & query_tokens]
    
    def validate_classification(self, llm_response_dict: dict, options: MergedRagResponseOption) -> PromptClassification:
        """
        Validate the LLM response against the provided options and return a PromptClassification object. 
        Logs warnings for any values that are invalid or not in the options list.

        Args:
            llm_response_dict: The raw dict parsed from the LLM response, expected to contain "correspondent", "document_type", and "tags" fields.
            options: MergedRagResponseOption containing the valid lists of correspondents, document types, and tags to validate against

        Returns:
            PromptClassification with validated fields; invalid values are set to None or empty list.        
        """        
        #check if correspondent is set and in the list
        correspondent = llm_response_dict.get("correspondent")
        if not isinstance(correspondent, str) or not correspondent.strip():
            correspondent = None
        if correspondent and correspondent not in options.correspondents:
            self.logging.warning(f"LLM returned a correspondent value that was not in the provided options: {correspondent}", color="yellow")
            correspondent = None

        #check if document_type is set and in the list
        document_type = llm_response_dict.get("document_type")
        if not isinstance(document_type, str) or not document_type.strip():
            document_type = None
        if document_type and document_type not in options.document_types:
            self.logging.warning(f"LLM returned a document_type value that was not in the provided options: {document_type}", color="yellow")
            document_type = None

        #check if tags is a list and all values are in the options
        raw_tags = llm_response_dict.get("tags")
        extracted_tags: list[str] = []
        if isinstance(raw_tags, list):
            tags = [t.strip() for t in raw_tags if isinstance(t, str) and t.strip()]        
            for tag in tags:
                if tag not in options.tags:
                    self.logging.warning(f"LLM returned a tag value that was not in the provided options: {tag}", color="yellow")
                else:
                    extracted_tags.append(tag)

        return PromptClassification(
            correspondent=correspondent,
            document_type=document_type,
            tags=extracted_tags,
        )
    
    ##########################################
    ################ Payloads ################
    ##########################################

    def create_classification_payload(self, options: MergedRagResponseOption, query: str, chat_history: list[dict] | None = None) -> list[dict]:
        """
        Generate the messages payload for the LLM classification request, including a dynamic system prompt with available filter options and the user query.

        Args:
            options: MergedRagResponseOption containing lists of correspondents, document types, and tags to be included in the system prompt.
            query: The raw user query string to be classified.
            chat_history: Optional prior conversation turns for context.

        Returns:
            List of message dicts to be sent to the LLM for classification.
        """
        system_prompt_prefix = (
        "You are a document filter extractor. "
        "Given a natural language query, extract the following document metadata filters. "
        "Return ONLY a JSON object with these three fields:\n"
        '  "correspondent": person or company name or null\n'
        '  "document_type": document category or null\n'
        '  "tags": list of topic keywords or []\n'
        "If a field cannot be confidently extracted from the query, return null or [].\n"
        "Do not include any explanation or markdown — only the raw JSON object.")

        system_prompt_suffix = (
        "\n\nIf the query mentions a name or type that closely matches one of the available "
        "values above, use the exact value from the list.")

        # Build dynamic system prompt
        option_lines: list[str] = []
        if options.correspondents:
            option_lines.append("Available correspondents: " + ", ".join(options.correspondents))
        if options.document_types:
            option_lines.append("Available document types: " + ", ".join(options.document_types))
        if options.tags:
            option_lines.append("Available tags: " + ", ".join(options.tags))

        if option_lines:
            system_prompt = (
                system_prompt_prefix + "\n\n" + "\n".join(option_lines) + system_prompt_suffix
            )
        else:
            system_prompt = system_prompt_prefix

        messages: list[dict] = [{"role": "system", "content": system_prompt}]
        if chat_history:
            messages.extend(chat_history)
        messages.append({
            "role": "user",
            "content": "Extract the document filters from this query as JSON: %s" % query,
        })
        return messages