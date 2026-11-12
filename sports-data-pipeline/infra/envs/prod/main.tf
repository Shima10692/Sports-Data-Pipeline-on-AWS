# prod environment. Resources arrive from phase 3 (storage) onwards.
#
# Naming rule: every resource is named "${var.project}-prod-..." and every IAM role
# sets permissions_boundary to the "${var.project}-boundary-prod" policy from the
# bootstrap stack. The prod apply role cannot create anything outside that.
