import pavilion.result.common
from pavilion.result_parsers import base_classes


class Filecheck(base_classes.ResultParser):
    """Checks the working directory for a given file.
    The parser will tell the user if the filename exists or not. """

    FORCE_DEFAULTS = ['match_select']

    def __init__(self):
        super().__init__(
            name='filecheck',
            description="Checks working directory for a given file. Globs are"
                        "accepted.",
            config_elems=[],
        )

    def check_args(self, **kwargs) -> dict:
        """This should always have match_select set to 'first'."""

        if kwargs.get('match_select') != base_classes.MATCH_FIRST:
            raise pavilion.result.common.ResultError(
                "You must use 'match_select: {}' with the filecheck parser. "
                "(it's the default)"
                .format(base_classes.MATCH_FIRST))

        return super().check_args(**kwargs)

    # pylint: disable=arguments-differ
    def __call__(self, file, filename=None):
        """Simply return True. The file exists if this is called."""
        return True
